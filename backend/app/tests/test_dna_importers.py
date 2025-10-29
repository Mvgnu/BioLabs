from pathlib import Path

import pytest

from app import models
from app.services import dna_assets
from app.services.importers import load_genbank, load_sbol, load_snapgene
from app.tests.conftest import TestingSessionLocal

FIXTURE_DIR = Path(__file__).parent / "data" / "importers"


def test_load_genbank_normalises_annotations():
    content = FIXTURE_DIR.joinpath("example.gb").read_bytes()
    result = load_genbank(content, filename="example.gb")

    assert result.name == "TESTPLASMID"
    assert result.topology == "circular"
    assert any(tag == "synthetic construct" for tag in result.tags)
    assert result.attachments and result.attachments[0].filename == "example.gb"
    payload = result.to_asset_payload()
    assert payload.metadata["topology"] == "circular"
    assert any(a.label == "example_cds" for a in payload.annotations)
    cds = next(ann for ann in payload.annotations if ann.label == "example_cds")
    assert cds.segments
    assert "cds" in cds.provenance_tags


def test_load_genbank_multi_segment_and_provenance_tags():
    content = FIXTURE_DIR.joinpath("segmented_regulatory.gb").read_bytes()
    result = load_genbank(content)

    payload = result.to_asset_payload()
    regulatory = next(
        ann for ann in payload.annotations if ann.feature_type.lower() == "regulatory"
    )
    cds = next(ann for ann in payload.annotations if ann.feature_type.lower() == "cds")
    operator = next(ann for ann in payload.annotations if ann.label == "operator_site")

    assert len(cds.segments) == 2
    assert cds.segments[0].start == 11
    assert cds.segments[1].strand == 1
    assert cds.qualifiers["experiment"] == "northern blot"
    assert "segmented protein" in cds.provenance_tags
    assert any(tag.endswith("promoter") for tag in regulatory.provenance_tags)
    assert regulatory.qualifiers["regulatory_class"] == "promoter"
    assert len(operator.segments) == 2
    assert operator.segments[0].strand == -1
    assert "repressor binding" in operator.provenance_tags


def test_load_sbol_generates_tracks():
    content = FIXTURE_DIR.joinpath("example.xml").read_text()
    result = load_sbol(content, filename="example.xml")

    assert result.sequence == "ATGCATGCATGC"
    assert result.metadata["roles"]
    assert all(isinstance(tag, str) for tag in result.tags)
    payload = result.to_asset_payload()
    assert payload.metadata["topology"] == "linear"
    assert payload.annotations[0].start == 1


def test_load_snapgene_fallback_json_bundle():
    content = FIXTURE_DIR.joinpath("example_snapgene.json").read_text()
    result = load_snapgene(content, filename="example.dna")

    assert result.sequence.startswith("ATGC")
    assert "snapgene" in result.tags
    assert result.metadata["topology"] == "circular"
    payload = result.to_asset_payload()
    assert any(ann.feature_type.lower() == "cds" for ann in payload.annotations)


@pytest.fixture
def viewer_asset():
    session = TestingSessionLocal()
    user = models.User(
        email="viewer@example.com",
        hashed_password="test",
        is_admin=True,
        is_active=True,
    )
    session.add(user)
    session.commit()
    importer_result = load_genbank(FIXTURE_DIR.joinpath("example.gb").read_text())
    asset = dna_assets.create_asset(
        session,
        payload=importer_result.to_asset_payload(),
        created_by=user,
    )
    session.commit()
    session.refresh(asset)
    session.refresh(asset.latest_version)
    yield asset
    session.close()


def test_build_viewer_payload_tracks_and_translations(viewer_asset):
    payload = dna_assets.build_viewer_payload(viewer_asset)

    assert payload.sequence.startswith("ATGC")
    assert payload.tracks[0].features
    cds_translation = next(
        (translation for translation in payload.translations if translation.label == "example_cds"),
        None,
    )
    assert cds_translation is not None
    assert cds_translation.amino_acids
    assert payload.guardrails.primers
    assert payload.analytics.codon_usage
    assert payload.analytics.gc_skew
    assert payload.analytics.thermodynamic_risk["overall_state"] in {"ok", "review"}
    assert payload.analytics.translation_frames["counts"]["+1"] >= 0
    assert payload.analytics.codon_adaptation_index >= 0.0
    assert isinstance(payload.analytics.motif_hotspots, list)
    assert "mitigations" in payload.analytics.thermodynamic_risk
