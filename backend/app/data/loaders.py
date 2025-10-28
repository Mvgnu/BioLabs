"""Cached data loaders for scientific reference catalogs."""

# purpose: expose cached loaders for sequence toolkit resources
# status: experimental
# depends_on: json, pathlib
# related_docs: docs/planning/cloning_planner_scope.md

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parent


def _load_json(path: Path) -> Any:
    """Return parsed JSON payload from disk."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def get_enzyme_catalog() -> tuple[dict[str, Any], ...]:
    """Return cached restriction enzyme metadata."""

    payload = _load_json(_BASE_DIR / "enzymes.json")
    return tuple(payload)


@lru_cache(maxsize=None)
def get_buffer_catalog() -> tuple[dict[str, Any], ...]:
    """Return cached reaction buffer metadata."""

    payload = _load_json(_BASE_DIR / "buffers.json")
    return tuple(payload)


@lru_cache(maxsize=None)
def get_assembly_strategy_catalog() -> tuple[dict[str, Any], ...]:
    """Return cached assembly strategy definitions."""

    payload = _load_json(_BASE_DIR / "assembly_strategies.json")
    return tuple(payload)


@lru_cache(maxsize=None)
def get_enzyme_kinetics_catalog() -> tuple[dict[str, Any], ...]:
    """Return cached enzyme kinetics descriptors."""

    payload = _load_json(_BASE_DIR / "enzyme_kinetics.json")
    return tuple(payload)


@lru_cache(maxsize=None)
def get_ligation_profile_catalog() -> tuple[dict[str, Any], ...]:
    """Return cached ligation efficiency profiles."""

    payload = _load_json(_BASE_DIR / "ligation_profiles.json")
    return tuple(payload)
