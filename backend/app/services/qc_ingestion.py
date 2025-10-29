"""Chromatogram and QC artifact ingestion helpers."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean
from typing import Any


def _normalise_signal(trace: Sequence[float]) -> list[float]:
    """Return baseline-corrected trace intensities."""

    # purpose: remove baseline offset before downstream QC heuristics
    if not trace:
        return []
    baseline = min(trace)
    return [value - baseline for value in trace]


def _signal_to_noise(trace: Sequence[float]) -> float:
    """Compute signal-to-noise ratio for a chromatogram trace."""

    # purpose: derive QC guardrail heuristics from chromatogram intensity profiles
    normalised = _normalise_signal(trace)
    if not normalised:
        return 0.0
    peak = max(normalised)
    noise_window = normalised[: len(normalised) // 10 or 1]
    noise = mean(noise_window) if noise_window else 0.0
    if noise <= 0:
        return float("inf") if peak > 0 else 0.0
    return peak / noise


def ingest_chromatograms(
    chromatograms: Sequence[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Normalise chromatogram metadata and compute guardrail heuristics."""

    # purpose: prepare QC artifacts for cloning planner guardrail gating
    # inputs: sequence of chromatogram descriptors from clients
    # outputs: dict containing normalised artifacts and guardrail metrics
    # status: experimental
    normalised: list[dict[str, Any]] = []
    guardrail_breaches: list[str] = []
    for entry in chromatograms or []:
        trace = entry.get("trace") or []
        snr = _signal_to_noise(trace)
        normalised.append(
            {
                "name": entry.get("name"),
                "sample_id": entry.get("sample_id"),
                "signal_to_noise": snr,
                "length": len(trace),
                "metadata": entry.get("metadata", {}),
            }
        )
        if snr and snr < 15:
            guardrail_breaches.append(
                f"Chromatogram {entry.get('name') or entry.get('sample_id') or '#'} has low SNR ({snr:.1f})"
            )
    return {
        "artifacts": normalised,
        "breaches": guardrail_breaches,
    }
