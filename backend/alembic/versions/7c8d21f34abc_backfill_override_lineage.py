"""backfill governance override lineage and enforce payload fidelity"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import select

# revision identifiers, used by Alembic.
revision: str = "7c8d21f34abc"
down_revision: str | Sequence[str] | None = "299f688b03e0"
branch_labels = None
depends_on = None


def _coerce_uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _ensure_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if value is not None}


def upgrade() -> None:
    connection = op.get_bind()

    overrides = sa.table(
        "governance_override_actions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("detail_snapshot", postgresql.JSON),
        sa.column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    lineages = sa.table(
        "governance_override_lineages",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("override_id", postgresql.UUID(as_uuid=True)),
    )

    existing_override_ids = {
        row.override_id
        for row in connection.execute(select(lineages.c.override_id))
        if getattr(row, "override_id", None) is not None
    }

    query = select(
        overrides.c.id,
        overrides.c.detail_snapshot,
        overrides.c.actor_id,
        overrides.c.created_at,
        overrides.c.updated_at,
    )
    results = connection.execute(query).fetchall()

    insert_rows: list[dict[str, Any]] = []

    for row in results:
        override_id = getattr(row, "id", None)
        if override_id is None or override_id in existing_override_ids:
            continue

        detail = row.detail_snapshot if isinstance(row.detail_snapshot, dict) else {}
        lineage_payload = detail.get("lineage") if isinstance(detail.get("lineage"), dict) else {}

        scenario_payload = None
        scenario_candidate = lineage_payload.get("scenario") if isinstance(lineage_payload.get("scenario"), dict) else None
        if scenario_candidate:
            scenario_payload = _ensure_snapshot(scenario_candidate)
        elif isinstance(detail.get("scenario"), dict):
            scenario_payload = _ensure_snapshot(detail["scenario"])

        notebook_payload = None
        notebook_candidate = lineage_payload.get("notebook_entry") if isinstance(lineage_payload.get("notebook_entry"), dict) else None
        if notebook_candidate:
            notebook_payload = _ensure_snapshot(notebook_candidate)
        elif isinstance(detail.get("notebook_entry"), dict):
            notebook_payload = _ensure_snapshot(detail["notebook_entry"])

        scenario_id = _coerce_uuid((scenario_payload or {}).get("id"))
        notebook_id = _coerce_uuid((notebook_payload or {}).get("id"))

        meta_payload = lineage_payload.get("metadata")
        if not isinstance(meta_payload, dict):
            meta_payload = detail.get("metadata") if isinstance(detail.get("metadata"), dict) else {}
        meta_payload = dict(_ensure_snapshot(meta_payload))
        meta_payload.setdefault("backfilled", True)

        captured_at = None
        if isinstance(lineage_payload.get("captured_at"), str):
            try:
                captured_at = datetime.fromisoformat(lineage_payload["captured_at"])
                if captured_at.tzinfo is None:
                    captured_at = captured_at.replace(tzinfo=timezone.utc)
            except ValueError:
                captured_at = None
        if captured_at is None:
            captured_at = getattr(row, "updated_at", None) or getattr(row, "created_at", None)
            if captured_at is None:
                captured_at = datetime.now(timezone.utc)
            elif captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=timezone.utc)

        insert_rows.append(
            {
                "id": uuid4(),
                "override_id": override_id,
                "scenario_id": scenario_id,
                "scenario_snapshot": scenario_payload or {},
                "notebook_entry_id": notebook_id,
                "notebook_snapshot": notebook_payload or {},
                "captured_by_id": getattr(row, "actor_id", None),
                "captured_at": captured_at,
                "metadata": meta_payload,
            }
        )

    if insert_rows:
        op.bulk_insert(
            sa.table(
                "governance_override_lineages",
                sa.column("id", postgresql.UUID(as_uuid=True)),
                sa.column("override_id", postgresql.UUID(as_uuid=True)),
                sa.column("scenario_id", postgresql.UUID(as_uuid=True)),
                sa.column("scenario_snapshot", postgresql.JSON),
                sa.column("notebook_entry_id", postgresql.UUID(as_uuid=True)),
                sa.column("notebook_snapshot", postgresql.JSON),
                sa.column("captured_by_id", postgresql.UUID(as_uuid=True)),
                sa.column("captured_at", sa.DateTime(timezone=True)),
                sa.column("metadata", postgresql.JSON),
            ),
            insert_rows,
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM governance_override_lineages WHERE metadata ->> 'backfilled' = 'true'")
    )
