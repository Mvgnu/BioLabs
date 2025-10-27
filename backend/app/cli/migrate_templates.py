"""CLI utilities for governance lifecycle migrations."""

# purpose: provide administrators with tooling to backfill governance snapshots
# status: pilot
# depends_on: backend.app.database, backend.app.models

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    from types import SimpleNamespace

    def _noop_echo(value: object) -> None:
        print(value)

    class _TyperStub:
        def __init__(self, help: str = "") -> None:
            self.help = help

        def command(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    def _option(default: object, **_kwargs) -> object:
        return default

    typer = SimpleNamespace(Typer=_TyperStub, Option=_option, echo=_noop_echo)
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal

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
