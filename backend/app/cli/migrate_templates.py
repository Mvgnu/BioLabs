"""CLI utilities for governance lifecycle migrations."""

# purpose: provide administrators with tooling to backfill governance snapshots
# status: pilot
# depends_on: backend.app.database, backend.app.models

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import UUID

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    from types import SimpleNamespace

    def _noop_echo(value: object) -> None:
        print(value)

    class _BadParameter(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)

    class _TyperStub:
        def __init__(self, help: str = "") -> None:
            self.help = help

        def command(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    def _option(default: object, **_kwargs) -> object:
        return default

    typer = SimpleNamespace(
        Typer=_TyperStub,
        Option=_option,
        echo=_noop_echo,
        BadParameter=_BadParameter,
    )
from sqlalchemy.orm import Session

from .. import models
from ..services import approval_ladders
from ..database import SessionLocal
from ..workers.packaging import enqueue_narrative_export_packaging

app = typer.Typer(help="Governance lifecycle maintenance commands")

_LOG_PATH = Path(__file__).resolve().parents[2] / "problems" / "governance_migration.log"


def _append_log(record: dict[str, object]) -> None:
    """Append a structured log entry to the governance migration log."""

    # purpose: capture anomalies discovered during governance migrations
    # inputs: dictionary payload describing anomaly context
    # outputs: serialized log line stored under problems/
    # status: pilot
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with _LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _iter_exports(session: Session) -> Iterable[models.ExecutionNarrativeExport]:
    return (
        session.query(models.ExecutionNarrativeExport)
        .filter(
            models.ExecutionNarrativeExport.workflow_template_id.isnot(None),
            models.ExecutionNarrativeExport.workflow_template_snapshot_id.is_(None),
        )
        .all()
    )


def migrate_exports(dry_run: bool = False) -> dict[str, int | bool]:
    """Bind legacy exports to immutable governance snapshots."""

    processed = 0
    anomalies = 0
    updated = 0
    session = SessionLocal()
    try:
        exports = _iter_exports(session)
        for export in exports:
            processed += 1
            template = export.workflow_template
            if not template:
                template = session.get(models.ExecutionNarrativeWorkflowTemplate, export.workflow_template_id)
            if not template:
                anomalies += 1
                _append_log(
                    {
                        "kind": "missing_template",
                        "export_id": str(export.id),
                        "template_id": str(export.workflow_template_id),
                    }
                )
                continue
            snapshot = template.published_snapshot
            if not snapshot:
                snapshot = (
                    session.query(models.ExecutionNarrativeWorkflowTemplateSnapshot)
                    .filter(models.ExecutionNarrativeWorkflowTemplateSnapshot.template_id == template.id)
                    .order_by(models.ExecutionNarrativeWorkflowTemplateSnapshot.version.desc())
                    .first()
                )
            if not snapshot:
                anomalies += 1
                _append_log(
                    {
                        "kind": "missing_snapshot",
                        "export_id": str(export.id),
                        "template_id": str(template.id),
                    }
                )
                continue
            if not dry_run:
                export.workflow_template_snapshot_id = snapshot.id
                export.workflow_template_snapshot = snapshot.snapshot_payload or {}
                export.workflow_template_key = template.template_key
                export.workflow_template_version = snapshot.version
            updated += 1
        if not dry_run and updated:
            session.commit()
        return {
            "processed": processed,
            "updated": updated,
            "anomalies": anomalies,
            "dry_run": dry_run,
        }
    finally:
        session.close()


@app.command("migrate-exports")
def migrate_exports_command(
    dry_run: bool = typer.Option(False, help="Perform a read-only migration check"),
) -> None:
    """CLI wrapper for :func:`migrate_exports`."""

    summary = migrate_exports(dry_run=dry_run)
    typer.echo(json.dumps(summary))


def queue_narrative_export(
    export_id: UUID | str,
    *,
    actor_email: str | None = None,
) -> dict[str, object]:
    """Enforce guardrails before queuing a narrative export for packaging."""

    # purpose: provide CLI/scheduler surfaces with shared dispatch semantics
    # inputs: export identifier, optional actor email for audit attribution
    # outputs: summary dict detailing queue outcome and gating metadata
    # status: pilot
    try:
        export_uuid = UUID(str(export_id))
    except ValueError as exc:
        raise ValueError("Invalid export identifier supplied") from exc

    session = SessionLocal()
    try:
        actor: models.User | None = None
        if actor_email:
            actor = (
                session.query(models.User)
                .filter(models.User.email == actor_email)
                .first()
            )
            if actor is None:
                raise ValueError("Actor email does not correspond to a known user")

        queued = approval_ladders.dispatch_export_for_packaging_by_id(
            session,
            export_id=export_uuid,
            actor=actor,
            enqueue=enqueue_narrative_export_packaging,
        )
        session.commit()

        export_snapshot = approval_ladders.load_export_with_ladder(
            session,
            export_id=export_uuid,
            include_guardrails=True,
        )
        guardrail_summary = None
        guardrail = getattr(export_snapshot, "guardrail_simulation", None)
        if guardrail is not None:
            guardrail_summary = getattr(getattr(guardrail, "summary", None), "state", None)

        pending_stage = export_snapshot.current_stage
        if pending_stage is None:
            for stage in export_snapshot.approval_stages:
                if stage.status in {"in_progress", "delegated", "pending"}:
                    pending_stage = stage
                    break

        return {
            "queued": queued,
            "export_id": str(export_uuid),
            "actor_id": str(actor.id) if actor else None,
            "approval_status": export_snapshot.approval_status,
            "artifact_status": export_snapshot.artifact_status,
            "pending_stage_id": str(pending_stage.id) if pending_stage else None,
            "pending_stage_status": pending_stage.status if pending_stage else None,
            "guardrail_state": guardrail_summary,
        }
    finally:
        session.close()


@app.command("queue-narrative-export")
def queue_narrative_export_command(
    export_id: str,
    actor_email: str = typer.Option(
        None,
        help="Optional actor email for attribution",
    ),
) -> None:
    """CLI wrapper for :func:`queue_narrative_export`."""

    try:
        summary = queue_narrative_export(export_id, actor_email=actor_email)
    except ValueError as exc:
        raise typer.BadParameter(str(exc))
    typer.echo(json.dumps(summary))
