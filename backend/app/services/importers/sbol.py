"""SBOL importer normalising XML SBOL documents into DNA assets."""

# purpose: convert SBOL v2 XML payloads into canonical DNAImportResult objects
# status: experimental
# depends_on: xml.etree.ElementTree
# related_docs: docs/dna_assets.md

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from typing import Any

from ...schemas import DNAAnnotationPayload
from .models import DNAImportAttachment, DNAImportResult

_SBOL_NS = {
    "sbol": "http://sbols.org/v2#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}


def _text(element: ET.Element | None, default: str = "") -> str:
    if element is None or element.text is None:
        return default
    return element.text.strip()


def _parse_annotations(root: ET.Element) -> list[DNAAnnotationPayload]:
    annotations: list[DNAAnnotationPayload] = []
    for annotation in root.findall(".//sbol:SequenceAnnotation", namespaces=_SBOL_NS):
        location = annotation.find("sbol:Location", namespaces=_SBOL_NS)
        if location is None:
            location = annotation.find("sbol:location/sbol:Location", namespaces=_SBOL_NS)
        if location is None:
            continue
        start = int(_text(location.find("sbol:start", namespaces=_SBOL_NS), "1"))
        end = int(_text(location.find("sbol:end", namespaces=_SBOL_NS), start))
        strand_val = _text(location.find("sbol:orientation", namespaces=_SBOL_NS), "+")
        strand = 1 if strand_val.endswith("inline") or strand_val.endswith("+1") else -1
        role = _text(annotation.find("sbol:role", namespaces=_SBOL_NS))
        annotations.append(
            DNAAnnotationPayload(
                label=_text(annotation.find("sbol:displayId", namespaces=_SBOL_NS)) or "feature",
                feature_type=role or "feature",
                start=start,
                end=end,
                strand=strand,
                qualifiers={
                    "role": role,
                    "orientation": strand_val,
                },
            )
        )
    return annotations


def load_sbol(data: bytes | str, *, filename: str | None = None) -> DNAImportResult:
    """Parse SBOL XML payloads into DNA asset import results."""

    # inputs: raw SBOL content with optional filename
    # outputs: DNAImportResult with topology and annotation metadata
    if isinstance(data, bytes):
        stream = io.BytesIO(data)
        content_bytes = data
    else:
        stream = io.StringIO(data)
        content_bytes = data.encode("utf-8")
    tree = ET.parse(stream)
    root = tree.getroot()

    component = root.find(".//sbol:ComponentDefinition", namespaces=_SBOL_NS)
    name = _text(component.find("sbol:displayId", namespaces=_SBOL_NS)) if component is not None else "Imported SBOL"
    description = _text(component.find("sbol:description", namespaces=_SBOL_NS)) if component is not None else ""
    roles = (
        [
            elem.attrib.get(f"{{{_SBOL_NS['rdf']}}}resource")
            for elem in component.findall("sbol:role", namespaces=_SBOL_NS)
        ]
        if component is not None
        else []
    )

    sequence_el = root.find(".//sbol:Sequence", namespaces=_SBOL_NS)
    sequence = _text(sequence_el.find("sbol:elements", namespaces=_SBOL_NS)) if sequence_el is not None else ""
    topology = _text(component.find("sbol:topology", namespaces=_SBOL_NS), "linear") if component is not None else "linear"

    annotations = _parse_annotations(root)
    attachments = []
    if filename:
        attachments.append(
            DNAImportAttachment(
                filename=filename,
                media_type="application/sbol+xml",
                content=content_bytes,
                metadata={"roles": roles},
            )
        )

    tags = []
    if "SO:0000987" in "".join(roles):
        tags.append("promoter")
    if topology == "circular":
        tags.append("circular")

    metadata: dict[str, Any] = {
        "description": description,
        "roles": roles,
        "topology": topology,
    }

    return DNAImportResult.from_payload(
        name=name or "Imported SBOL",
        sequence=sequence,
        topology=topology,
        annotations=annotations,
        metadata={k: v for k, v in metadata.items() if v},
        tags=tags,
        source_format="sbol",
        attachments=attachments,
    )
