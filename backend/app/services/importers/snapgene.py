"""SnapGene importer converting binary or JSON SnapGene exports into DNA assets."""

# purpose: convert SnapGene uploads into canonical DNAImportResult objects
# status: experimental
# depends_on: json, zipfile
# related_docs: docs/dna_assets.md

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from ...schemas import DNAAnnotationPayload
from .models import DNAImportAttachment, DNAImportResult


def _load_with_library(data: bytes) -> dict[str, Any] | None:
    """Attempt to parse SnapGene binary data using snapgene_reader if available."""

    # purpose: use third-party parser when installed for full fidelity imports
    try:
        from snapgene_reader import snapgene  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - optional dependency
        return None
    stream = io.BytesIO(data)
    reader = snapgene.SnapGeneFileReader(stream)
    record = reader.read()
    sequence = record.sequence.decode("utf-8") if isinstance(record.sequence, bytes) else record.sequence
    features = []
    for feature in record.features or []:
        for segment in feature.segments:
            features.append(
                {
                    "label": feature.name or feature.type or "feature",
                    "type": feature.type or "feature",
                    "start": int(segment.start) + 1,
                    "end": int(segment.end),
                    "strand": 1 if not getattr(segment, "strand", False) else segment.strand,
                    "qualifiers": feature.qualifiers or {},
                }
            )
    return {
        "name": record.name or "SnapGene Import",
        "sequence": sequence,
        "topology": "circular" if getattr(record, "is_circular", False) else "linear",
        "features": features,
        "metadata": {
            "author": getattr(record, "author", ""),
            "comments": getattr(record, "comments", ""),
        },
    }


def _load_json_bundle(data: bytes) -> dict[str, Any] | None:
    """Parse a lightweight SnapGene JSON bundle used for tests and fallbacks."""

    # purpose: support deterministic fixtures when binary reader unavailable
    stream = io.BytesIO(data)
    try:
        with zipfile.ZipFile(stream) as archive:
            if "snapgene.json" not in archive.namelist():
                return None
            payload = json.loads(archive.read("snapgene.json"))
            return payload
    except zipfile.BadZipFile:
        pass

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalise_feature(descriptor: dict[str, Any]) -> DNAAnnotationPayload:
    """Convert SnapGene feature descriptors into annotation payloads."""

    # purpose: standardise SnapGene features for dna asset annotations
    return DNAAnnotationPayload(
        label=descriptor.get("label") or descriptor.get("name") or descriptor.get("type", "feature"),
        feature_type=descriptor.get("type", "feature"),
        start=int(descriptor.get("start", 1)),
        end=int(descriptor.get("end", 1)),
        strand=int(descriptor.get("strand", 1)) if descriptor.get("strand") is not None else None,
        qualifiers=dict(descriptor.get("qualifiers") or {}),
    )


def load_snapgene(data: bytes | str, *, filename: str | None = None) -> DNAImportResult:
    """Parse SnapGene data into a DNA import result."""

    # inputs: binary or JSON-wrapped SnapGene export
    # outputs: DNAImportResult with annotations and provenance tags
    if isinstance(data, str):
        binary = data.encode("utf-8")
    else:
        binary = data
    library_record = _load_with_library(binary)
    record = library_record or _load_json_bundle(binary)
    if record is None:
        raise ValueError("Unsupported SnapGene payload")

    annotations = [_normalise_feature(feature) for feature in record.get("features", [])]
    topology = record.get("topology", "linear")
    tags = ["snapgene"]
    if topology == "circular":
        tags.append("circular")

    attachments = []
    if filename:
        attachments.append(
            DNAImportAttachment(
                filename=filename,
                media_type="application/vnd.snapgene",
                content=binary,
                metadata={"import_mode": "library" if library_record else "json"},
            )
        )

    metadata = dict(record.get("metadata") or {})
    metadata.setdefault("topology", topology)
    metadata.setdefault("source_format", "snapgene")

    return DNAImportResult.from_payload(
        name=record.get("name") or "SnapGene Import",
        sequence=record.get("sequence", ""),
        topology=topology,
        annotations=annotations,
        metadata=metadata,
        tags=tags,
        source_format="snapgene",
        attachments=attachments,
    )
