"""Unit tests covering governance simulation grouping and diffs."""

# purpose: validate stage-aware simulation helpers with baseline diffs
# status: pilot

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app import simulation


def _make_step(
    *,
    blocked_reason: str | None = None,
    required_actions: list[str] | None = None,
    auto_triggers: list[str] | None = None,
):
    """Return a lightweight step state namespace used for simulation tests."""

    # purpose: fabricate minimal step telemetry used by simulation aggregator
    # inputs: optional blocker metadata mirrors ExperimentStepStatus attributes
    # outputs: SimpleNamespace mimicking the simulation contract
    # status: pilot
    return SimpleNamespace(
        blocked_reason=blocked_reason,
        required_actions=list(required_actions or []),
        auto_triggers=list(auto_triggers or []),
    )


def test_build_stage_simulation_groups_steps_and_applies_overrides() -> None:
    """Simulation should respect blueprint mapping and produce diff snapshots."""

    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    baseline_assignee = uuid4()
    baseline_delegate = uuid4()
    override_assignee = uuid4()

    stage_blueprint = [
        {
            "name": "Draft Review",
            "required_role": "scientist",
            "sla_hours": 12,
            "stage_step_indexes": [0, 1],
        },
        {
            "name": "Compliance",
            "required_role": "quality",
            "sla_hours": 18,
            "stage_gate_keys": ["qc"],
            "metadata": {
                "assignee_id": str(baseline_assignee),
                "delegate_id": str(baseline_delegate),
            },
        },
    ]

    step_states = [
        _make_step(blocked_reason="Inventory missing", required_actions=["inventory:link"]),
        _make_step(),
        _make_step(blocked_reason="QC approval pending", auto_triggers=["notify:qc"]),
    ]

    step_requirements = {
        2: {"gate_key": "qc"},
    }

    overrides = {
        1: {
            "assignee_id": override_assignee,
            "sla_hours": 24,
        }
    }

    results = simulation.build_stage_simulation(
        stage_blueprint,
        default_stage_sla_hours=None,
        stage_overrides=overrides,
        step_states=step_states,
        step_requirements=step_requirements,
        generated_at=now,
    )

    assert len(results) == 2

    first_stage = results[0]
    assert first_stage.mapped_step_indexes == [0, 1]
    assert first_stage.baseline.status == "blocked"
    assert first_stage.simulated.status == "blocked"
    assert first_stage.baseline.sla_hours == 12
    assert first_stage.simulated.sla_hours == 12
    assert first_stage.baseline.projected_due_at == now + timedelta(hours=12)

    second_stage = results[1]
    assert second_stage.mapped_step_indexes == [2]
    assert second_stage.gate_keys == ["qc"]
    assert second_stage.baseline.blockers == ["QC approval pending"]
    assert second_stage.simulated.blockers == ["QC approval pending"]
    assert second_stage.baseline.assignee_id == baseline_assignee
    assert second_stage.simulated.assignee_id == override_assignee
    assert second_stage.baseline.delegate_id == baseline_delegate
    assert second_stage.simulated.delegate_id == baseline_delegate
    assert second_stage.baseline.sla_hours == 18
    assert second_stage.simulated.sla_hours == 24
    assert second_stage.simulated.projected_due_at == now + timedelta(
        hours=36
    )
    assert second_stage.baseline.projected_due_at == now + timedelta(
        hours=30
    )
    assert second_stage.simulated.projected_due_at > second_stage.baseline.projected_due_at


def test_evaluate_reversal_guardrails_detects_regressions() -> None:
    """Guardrail evaluation should flag regressions introduced by reversal payloads."""

    generated_at = datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc)
    baseline_due = generated_at + timedelta(hours=6)
    simulated_due = baseline_due + timedelta(hours=2)

    comparison_items = [
        simulation.StageSimulationComparison(
            index=0,
            name="Draft",
            required_role="scientist",
            mapped_step_indexes=[0],
            gate_keys=[],
            baseline=simulation.StageSimulationSnapshot(
                status="ready",
                sla_hours=6,
                projected_due_at=baseline_due,
                blockers=[],
                required_actions=[],
                auto_triggers=[],
                assignee_id=None,
                delegate_id=None,
            ),
            simulated=simulation.StageSimulationSnapshot(
                status="blocked",
                sla_hours=8,
                projected_due_at=simulated_due,
                blockers=["Inventory missing"],
                required_actions=["inventory:link"],
                auto_triggers=[],
                assignee_id=None,
                delegate_id=None,
            ),
        ),
        simulation.StageSimulationComparison(
            index=1,
            name="QC",
            required_role="quality",
            mapped_step_indexes=[1],
            gate_keys=[],
            baseline=simulation.StageSimulationSnapshot(
                status="blocked",
                sla_hours=12,
                projected_due_at=None,
                blockers=["Awaiting QC"],
                required_actions=[],
                auto_triggers=[],
                assignee_id=None,
                delegate_id=None,
            ),
            simulated=simulation.StageSimulationSnapshot(
                status="blocked",
                sla_hours=12,
                projected_due_at=None,
                blockers=["Awaiting QC"],
                required_actions=[],
                auto_triggers=[],
                assignee_id=None,
                delegate_id=None,
            ),
        ),
    ]

    summary = simulation.evaluate_reversal_guardrails(comparison_items)
    assert summary.state == "blocked"
    assert 0 in summary.regressed_stage_indexes
    assert summary.projected_delay_minutes == 120
    assert any(reason.startswith("stage_0:status_regression") for reason in summary.reasons)
    assert any(reason.startswith("stage_0:sla_increase_hours") for reason in summary.reasons)
    assert any(reason.startswith("stage_0:due_delay_minutes") for reason in summary.reasons)


def test_evaluate_reversal_guardrails_clear_when_no_regressions() -> None:
    """Guardrail evaluation should return clear when simulated stages improve."""

    generated_at = datetime(2024, 2, 1, 8, 30, tzinfo=timezone.utc)
    comparison_items = [
        simulation.StageSimulationComparison(
            index=0,
            name="Draft",
            required_role="scientist",
            mapped_step_indexes=[0],
            gate_keys=[],
            baseline=simulation.StageSimulationSnapshot(
                status="blocked",
                sla_hours=10,
                projected_due_at=generated_at + timedelta(hours=10),
                blockers=["Needs attachments"],
                required_actions=[],
                auto_triggers=[],
                assignee_id=None,
                delegate_id=None,
            ),
            simulated=simulation.StageSimulationSnapshot(
                status="ready",
                sla_hours=8,
                projected_due_at=generated_at + timedelta(hours=8),
                blockers=[],
                required_actions=[],
                auto_triggers=[],
                assignee_id=None,
                delegate_id=None,
            ),
        )
    ]

    summary = simulation.evaluate_reversal_guardrails(comparison_items)
    assert summary.state == "clear"
    assert summary.reasons == []
    assert summary.regressed_stage_indexes == []
    assert summary.projected_delay_minutes == 0

