"""Celery worker for resilient narrative export packaging."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import SessionLocal
from ..eventlog import record_execution_event
from ..storage import load_binary_payload, save_binary_payload, validate_checksum
from ..tasks import celery_app

# purpose: manage durable execution narrative packaging outside request lifecycle
# inputs: export identifiers to process, storage configuration, retry policy env vars
# outputs: persisted artifact metadata, lifecycle audit events, storage handles
# status: pilot

_logger = get_task_logger(__name__)

MAX_RETRIES = int(os.getenv("NARRATIVE_PACKAGING_MAX_RETRIES", "5"))
RETRY_BACKOFF_SECONDS = int(os.getenv("NARRATIVE_PACKAGING_RETRY_SECONDS", "60"))
RETENTION_DAYS = int(os.getenv("NARRATIVE_EXPORT_RETENTION_DAYS", "365"))


def enqueue_narrative_export_packaging(export_id: UUID | str) -> None:
    """Dispatch a narrative export for asynchronous packaging."""

    identifier = str(export_id)
    if celery_app.conf.task_always_eager:
        package_execution_narrative_export(identifier)
    else:
        package_execution_narrative_export.delay(identifier)


def _build_export_artifact_payload(
    export: models.ExecutionNarrativeExport,
    db_session: Session,
) -> tuple[bytes, list[dict[str, Any]]]:
    """Return zipped dossier bytes and manifest for a narrative export."""

    buffer = io.BytesIO()
    archive = zipfile.ZipFile(file=buffer, mode="w", compression=zipfile.ZIP_DEFLATED)
    attachments_manifest: list[dict[str, Any]] = []

    export_metadata = {
        "export_id": str(export.id),
        "execution_id": str(export.execution_id),
        "version": export.version,
        "generated_at": export.generated_at.isoformat(),
        "event_count": export.event_count,
        "notes": export.notes,
        "metadata": export.meta or {},
        "requested_by": str(export.requested_by_id),
    }

    archive.writestr("narrative.md", export.content)
    archive.writestr("export.json", json.dumps(export_metadata, indent=2, default=str))

    for index, attachment in enumerate(export.attachments, start=1):
        manifest_entry: dict[str, Any] = {
            "id": str(attachment.id),
            "type": attachment.evidence_type,
            "reference_id": str(attachment.reference_id),
            "label": attachment.label,
            "snapshot": attachment.snapshot or {},
        }
        if attachment.evidence_type == "file" and attachment.file_id:
            file_obj = attachment.file
            if not file_obj:
                file_obj = (
                    db_session.query(models.File)
                    .filter(models.File.id == attachment.file_id)
                    .first()
                )
            if not file_obj:
                raise FileNotFoundError("Attachment file missing for export packaging")
            file_bytes = load_binary_payload(file_obj.storage_path)
            safe_label = attachment.label or file_obj.filename or f"attachment-{index}"
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", safe_label) or f"attachment-{index}.bin"
            file_path = f"attachments/files/{index:02d}-{safe_name}"
            archive.writestr(file_path, file_bytes)
            manifest_entry["file"] = {
                "id": str(file_obj.id),
                "filename": file_obj.filename,
                "path": file_path,
                "size": file_obj.file_size,
                "type": file_obj.file_type,
            }
        attachments_manifest.append(manifest_entry)

    archive.writestr(
        "attachments.json",
        json.dumps(attachments_manifest, indent=2, default=str),
    )
    archive.close()

    return buffer.getvalue(), attachments_manifest


@celery_app.task(bind=True, name="app.workers.packaging.package_execution_narrative_export")
def package_execution_narrative_export(self, export_identifier: str) -> str:
    """Generate zipped dossier artifact for a persisted narrative export."""

    try:
        export_uuid = UUID(str(export_identifier))
    except ValueError:
        _logger.warning("Rejecting packaging request with invalid identifier %s", export_identifier)
        return "invalid"

    db = SessionLocal()
    try:
        export = (
            db.query(models.ExecutionNarrativeExport)
            .options(
                joinedload(models.ExecutionNarrativeExport.execution),
                joinedload(models.ExecutionNarrativeExport.requested_by),
                joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                    models.ExecutionNarrativeExportAttachment.file
                ),
            )
            .filter(models.ExecutionNarrativeExport.id == export_uuid)
            .first()
        )
        if not export:
            _logger.warning("Narrative export %s missing", export_uuid)
            return "missing"

        if export.artifact_status == "ready" and export.artifact_file_id:
            return "noop"

        attempt = export.packaging_attempts + 1
        export.packaging_attempts = attempt
        export.artifact_status = "processing" if attempt == 1 else "retrying"
        export.artifact_error = None
        record_execution_event(
            db,
            export.execution,
            "narrative_export.packaging.started" if attempt == 1 else "narrative_export.packaging.retrying",
            {
                "export_id": str(export.id),
                "version": export.version,
                "attempt": attempt,
            },
            actor=export.requested_by,
        )
        db.commit()

        try:
            archive_bytes, manifest = _build_export_artifact_payload(export, db)
            storage_namespace = f"narratives/{export.execution_id}/v{export.version}"
            storage_path, file_size = save_binary_payload(
                archive_bytes,
                f"execution-{export.execution_id}-narrative-v{export.version}.zip",
                content_type="application/zip",
                namespace=storage_namespace,
                encrypt=os.getenv("NARRATIVE_EXPORT_ENCRYPTION", "0") == "1",
            )
            checksum = hashlib.sha256(archive_bytes).hexdigest()
            manifest_digest = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            if not validate_checksum(storage_path, checksum):
                raise ValueError("Stored artifact checksum does not match generated archive")

            artifact_file = models.File(
                id=uuid4(),
                filename=f"execution_{export.execution_id}_narrative_v{export.version}.zip",
                file_type="application/zip",
                file_size=file_size,
                storage_path=storage_path,
                uploaded_by=export.requested_by_id,
            )
            artifact_file.meta = {
                "source": "execution_narrative_export",
                "export_id": str(export.id),
                "version": export.version,
                "attachments": manifest,
                "checksum": checksum,
                "manifest_digest": manifest_digest,
            }

            packaged_at = datetime.now(timezone.utc)
            export.artifact_file_id = artifact_file.id
            export.artifact_file = artifact_file
            export.artifact_checksum = checksum
            export.artifact_manifest_digest = manifest_digest
            export.artifact_status = "ready"
            export.packaged_at = packaged_at
            export.retention_expires_at = packaged_at + timedelta(days=RETENTION_DAYS)
            export.artifact_error = None

            db.add(artifact_file)
            record_execution_event(
                db,
                export.execution,
                "narrative_export.packaging.ready",
                {
                    "export_id": str(export.id),
                    "version": export.version,
                    "artifact_file_id": str(artifact_file.id),
                    "checksum": checksum,
                    "attempt": attempt,
                },
                actor=export.requested_by,
            )
            db.commit()
            return storage_path
        except Exception as exc:  # pragma: no cover - validated in tests via failure simulation
            export.artifact_status = "failed" if attempt >= MAX_RETRIES else "retrying"
            export.artifact_error = str(exc)
            record_execution_event(
                db,
                export.execution,
                "narrative_export.packaging.failed",
                {
                    "export_id": str(export.id),
                    "version": export.version,
                    "attempt": attempt,
                    "error": str(exc),
                },
                actor=export.requested_by,
            )
            db.commit()
            if attempt < MAX_RETRIES:
                raise self.retry(exc=exc, countdown=RETRY_BACKOFF_SECONDS * attempt)
            return "failed"
    finally:
        db.close()


def get_packaging_queue_snapshot() -> dict[str, Any]:
    """Return a lightweight view into Celery queue state for packaging jobs."""

    inspector = celery_app.control.inspect()
    snapshot = {
        "active": 0,
        "scheduled": 0,
        "reserved": 0,
    }
    if not inspector:
        return snapshot

    active = inspector.active() or {}
    reserved = inspector.reserved() or {}
    scheduled = inspector.scheduled() or {}

    snapshot["active"] = sum(len(tasks) for tasks in active.values()) if isinstance(active, dict) else 0
    snapshot["reserved"] = (
        sum(len(tasks) for tasks in reserved.values()) if isinstance(reserved, dict) else 0
    )
    snapshot["scheduled"] = (
        sum(len(tasks) for tasks in scheduled.values()) if isinstance(scheduled, dict) else 0
    )
    return snapshot

