"""GenBank importer normalising sequence records into DNA assets."""

# purpose: convert GenBank uploads into canonical DNAImportResult payloads
# status: experimental
# depends_on: Bio.SeqIO, backend.app.services.importers.models
# related_docs: docs/dna_assets.md

from __future__ import annotations

import io
from typing import Any

from Bio import SeqIO
from Bio.SeqFeature import CompoundLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from ...schemas import DNAAnnotationPayload
from .models import DNAImportAttachment, DNAImportResult


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _segment_map(location: Any) -> list[dict[str, int]]:
    """Normalise feature locations (including compound joins) into segments."""

    # purpose: preserve multi-segment CDS/regulatory coordinates for viewer overlays
    segments: list[dict[str, int]] = []
    parts = []
    if isinstance(location, CompoundLocation):
        parts = list(location.parts)
    elif hasattr(location, "start") and hasattr(location, "end"):
        parts = [location]
    for part in parts:
        strand = getattr(part, "strand", None)
        if strand is None and hasattr(location, "strand"):
            strand = getattr(location, "strand")
        segments.append(
            {
                "start": int(part.start) + 1,
                "end": int(part.end),
                "strand": strand,
            }
        )
    segments.sort(key=lambda value: value["start"])
    return segments


def _normalise_provenance_tags(feature: SeqFeature) -> list[str]:
    """Extract provenance tags from feature qualifiers."""

    # purpose: align annotation provenance with governance metadata expectations
    tag_keys = {
        "gene",
        "product",
        "note",
        "locus_tag",
        "experiment",
        "regulatory_class",
        "source",
        "protein_id",
        "function",
        "bound_moiety",
    }
    tags: set[str] = set()
    feature_type = feature.type or ""
    if feature_type:
        tags.add(feature_type.lower())
    for key in tag_keys:
        values = feature.qualifiers.get(key)
        if not values:
            continue
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            if key == "note":
                if ":" in text:
                    _, _, remainder = text.partition(":")
                    text = remainder.strip() or text
                fragments = [fragment.strip() for fragment in text.split(";") if fragment.strip()]
                if fragments:
                    tags.update(fragment.lower() for fragment in fragments)
                    continue
            tags.add(text.lower())
    return sorted(tags)


def _coerce_annotation(feature: SeqFeature) -> DNAAnnotationPayload:
    """Convert a BioPython feature into an annotation payload."""

    # purpose: translate GenBank feature coordinates into viewer annotations
    location = feature.location
    start = int(location.start) + 1
    end = int(location.end)
    qualifiers: dict[str, Any] = {}
    for key, values in (feature.qualifiers or {}).items():
        if isinstance(values, list) and len(values) == 1:
            qualifiers[key] = values[0]
        else:
            qualifiers[key] = values
    label = _first(feature.qualifiers.get("label")) or _first(feature.qualifiers.get("gene"))
    segments = _segment_map(location)
    if segments:
        start = min(segment["start"] for segment in segments)
        end = max(segment["end"] for segment in segments)
    return DNAAnnotationPayload(
        label=label or feature.type or "feature",
        feature_type=feature.type or "feature",
        start=start,
        end=end,
        strand=location.strand,
        qualifiers=qualifiers,
        segments=segments,
        provenance_tags=_normalise_provenance_tags(feature),
    )


def _extract_metadata(record: SeqRecord) -> dict[str, Any]:
    """Gather record annotations relevant to DNA asset metadata."""

    # purpose: preserve source annotations and provenance for governance
    annotations = dict(record.annotations or {})
    organism = annotations.get("organism")
    source = annotations.get("source")
    return {
        "definition": annotations.get("comment") or annotations.get("definition"),
        "organism": organism,
        "source": source,
        "topology": annotations.get("topology", "linear"),
        "references": [ref.title for ref in annotations.get("references", []) if getattr(ref, "title", None)],
    }


def load_genbank(data: bytes | str, *, filename: str | None = None) -> DNAImportResult:
    """Parse GenBank content and normalise it into an import result."""

    # inputs: raw GenBank file content and optional filename for attachments
    # outputs: DNAImportResult consumable by dna_assets ingestion
    if isinstance(data, bytes):
        buffer = io.StringIO(data.decode("utf-8"))
    else:
        buffer = io.StringIO(data)
    record: SeqRecord = SeqIO.read(buffer, "genbank")
    annotations = [
        _coerce_annotation(feature)
        for feature in record.features
        if feature.type not in {"source"}
    ]
    metadata = _extract_metadata(record)
    topology = metadata.get("topology", "linear")
    attachments = []
    if filename:
        attachments.append(
            DNAImportAttachment(
                filename=filename,
                media_type="chemical/seq-na-genbank",
                content=data.encode("utf-8") if isinstance(data, str) else data,
                metadata={"record_id": record.id},
            )
        )
    tags = []
    if topology == "circular":
        tags.append("circular")
    if organism := metadata.get("organism"):
        tags.append(organism.lower())
    return DNAImportResult.from_payload(
        name=record.name or record.id,
        sequence=str(record.seq),
        topology=topology,
        annotations=annotations,
        metadata={
            "length": len(record.seq),
            "source_format": "genbank",
            **{k: v for k, v in metadata.items() if v},
        },
        tags=tags,
        source_format="genbank",
        attachments=attachments,
    )
