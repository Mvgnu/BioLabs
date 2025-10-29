"""Normalized DNA import descriptors used by importer adapters."""

# purpose: define canonical payloads bridging file importers and dna asset ingestion
# status: experimental
# related_docs: docs/dna_assets.md

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ...schemas import DNAAnnotationPayload, DNAAssetCreate


@dataclass(slots=True)
class DNAImportAttachment:
    """Attachment metadata derived during DNA imports."""

    # purpose: represent supplementary files (e.g., original uploads, chromatograms)
    # status: experimental
    filename: str
    media_type: str
    content: bytes
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DNAImportResult:
    """Canonical representation of importer-normalised DNA payloads."""

    # purpose: capture asset creation payloads plus topology + provenance metadata
    name: str
    sequence: str
    topology: str
    annotations: list[DNAAnnotationPayload] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source_format: str = "unknown"
    attachments: list[DNAImportAttachment] = field(default_factory=list)

    def to_asset_payload(self, *, team_id: str | None = None) -> DNAAssetCreate:
        """Convert the normalized import into a DNA asset creation payload."""

        # inputs: optional team identifier for asset scoping
        # outputs: DNAAssetCreate payload with importer annotations and tags
        payload_metadata = dict(self.metadata)
        payload_metadata.setdefault("topology", self.topology)
        payload_metadata.setdefault("source_format", self.source_format)
        return DNAAssetCreate(
            name=self.name,
            sequence=self.sequence,
            team_id=team_id,
            metadata=payload_metadata,
            tags=list(self.tags),
            annotations=list(self.annotations),
        )

    @classmethod
    def from_payload(
        cls,
        *,
        name: str,
        sequence: str,
        topology: str,
        annotations: Iterable[DNAAnnotationPayload] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        source_format: str,
        attachments: Iterable[DNAImportAttachment] | None = None,
    ) -> "DNAImportResult":
        """Construct a result instance from importer components."""

        return cls(
            name=name,
            sequence=sequence,
            topology=topology,
            annotations=list(annotations or []),
            metadata=dict(metadata or {}),
            tags=list(tags or []),
            source_format=source_format,
            attachments=list(attachments or []),
        )
