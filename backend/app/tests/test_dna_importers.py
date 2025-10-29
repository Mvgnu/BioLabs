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
