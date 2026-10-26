"""
tests/test_anomaly_rules.py

Unit tests for AnomalyDetectorAgent — the deterministic rule engine.

These tests need no ERPNext instance and no LLM key, which is the whole point
of keeping detection rules out of prompts: the logic that decides whether a
payroll record is suspicious is a pure function of the ComparisonRecord, so it
can be pinned down exactly.

Every test goes through the public `run()` method rather than the private
`_detect_reasons()`, so the tests describe the agent's contract and not its
internals.
"""

from agents.anomaly import AnomalyDetectorAgent
from schemas.models import ComparisonRecord

THRESHOLD = 15.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def record(**overrides) -> ComparisonRecord:
    """Build a ComparisonRecord with sensible identity fields."""
    base = {
        "employee_id": "HR-EMP-00001",
        "employee_name": "Asha Verma",
    }
    base.update(overrides)
    return ComparisonRecord(**base)


def reasons_for(rec: ComparisonRecord, threshold: float = THRESHOLD) -> list[str]:
    """Run the agent over a single record and return its anomaly reasons."""
    flagged = AnomalyDetectorAgent(threshold_pct=threshold).run([rec])
    return flagged[0].anomaly_reasons if flagged else []


# ---------------------------------------------------------------------------
# Rule 1 / Rule 2 — presence of a slip
# ---------------------------------------------------------------------------


def test_new_employee_is_flagged():
    """No previous slip but a current one — the employee just joined."""
    rec = record(prev_net=None, curr_net=52_000.0)
    assert reasons_for(rec) == ["new_employee"]


def test_new_employee_short_circuits_other_rules():
    """
    A new employee has no payroll history, so comparing deduction components
    against an absent slip is meaningless. Rule 1 must return immediately.
    """
    rec = record(
        prev_net=None,
        curr_net=52_000.0,
        missing_deduction_components=["Provident Fund"],
    )
    assert reasons_for(rec) == ["new_employee"]


def test_missing_slip_is_flagged():
    """Employee was paid last month but has no slip this month."""
    rec = record(prev_net=48_000.0, curr_net=None)
    assert reasons_for(rec) == ["missing_slip"]


def test_missing_slip_short_circuits_other_rules():
    """
    Regression guard: an absent current slip previously caused every previous
    deduction component to be reported as "missing". Rule 2 must return early.
    """
    rec = record(
        prev_net=48_000.0,
        curr_net=None,
        missing_deduction_components=["Provident Fund", "Professional Tax"],
    )
    assert reasons_for(rec) == ["missing_slip"]


# ---------------------------------------------------------------------------
# Rule 3 — net pay movement against the threshold
# ---------------------------------------------------------------------------


def test_net_change_above_threshold_is_flagged():
    rec = record(prev_net=40_000.0, curr_net=49_000.0, net_delta_pct=22.5)
    assert "large_net_change" in reasons_for(rec)


def test_net_change_below_threshold_is_not_flagged():
    rec = record(prev_net=40_000.0, curr_net=43_600.0, net_delta_pct=9.0)
    assert reasons_for(rec) == []


def test_threshold_boundary_is_exclusive():
    """A change of exactly the threshold is not an anomaly — the rule is `>`."""
    assert reasons_for(record(net_delta_pct=15.0)) == []
    assert reasons_for(record(net_delta_pct=15.1)) == ["large_net_change"]


def test_large_drop_is_flagged_as_well_as_a_rise():
    """The rule compares magnitude, so a pay cut is just as suspicious."""
    rec = record(prev_net=60_000.0, curr_net=36_000.0, net_delta_pct=-40.0)
    assert "large_net_change" in reasons_for(rec)


def test_custom_threshold_overrides_the_configured_one():
    """A stricter threshold flags a change the default would let through."""
    rec = record(net_delta_pct=9.0)
    assert reasons_for(rec, threshold=15.0) == []
    assert reasons_for(rec, threshold=5.0) == ["large_net_change"]


def test_default_threshold_comes_from_settings():
    """With no override the agent uses ANOMALY_THRESHOLD_PCT from config."""
    assert AnomalyDetectorAgent().threshold_pct == 15.0


# ---------------------------------------------------------------------------
# Rules 4-6 — deduction anomalies
# ---------------------------------------------------------------------------


def test_removed_deduction_component_is_flagged():
    """Component-level evidence: a deduction that existed last month is gone."""
    rec = record(
        prev_net=40_000.0,
        curr_net=40_200.0,
        net_delta_pct=0.5,
        missing_deduction_components=["Provident Fund"],
    )
    assert reasons_for(rec) == ["missing_deduction"]


def test_deductions_dropped_to_zero_with_flat_gross_is_flagged():
    """
    Fallback for when component detail is unavailable: total deductions went
    from positive to exactly zero while gross pay stayed put.
    """
    rec = record(
        prev_gross=60_000.0,
        curr_gross=60_000.0,
        prev_deductions=3_200.0,
        curr_deductions=0.0,
        deduction_delta=-3_200.0,
        net_delta_pct=5.6,
    )
    assert reasons_for(rec) == ["missing_deduction"]


def test_deduction_change_with_flat_gross_is_flagged():
    """
    Deductions moved by more than the absolute threshold while gross pay did
    not — a deduction was edited without a matching salary change.
    """
    rec = record(
        prev_gross=60_000.0,
        curr_gross=60_000.0,
        prev_deductions=3_200.0,
        curr_deductions=2_400.0,
        deduction_delta=-800.0,
        net_delta_pct=1.4,
    )
    assert reasons_for(rec) == ["deduction_anomaly"]


def test_small_deduction_change_is_not_flagged():
    """Below the absolute deduction threshold this is ordinary month-to-month noise."""
    rec = record(
        prev_gross=60_000.0,
        curr_gross=60_000.0,
        prev_deductions=3_200.0,
        curr_deductions=2_900.0,
        deduction_delta=-300.0,
        net_delta_pct=0.5,
    )
    assert reasons_for(rec) == []


def test_deduction_change_alongside_a_gross_change_is_not_flagged():
    """
    When gross pay also moved, the deduction change has an obvious cause
    (a salary revision), so the deduction rules deliberately stay quiet.
    """
    rec = record(
        prev_gross=60_000.0,
        curr_gross=65_000.0,
        prev_deductions=3_200.0,
        curr_deductions=2_400.0,
        deduction_delta=-800.0,
        net_delta_pct=9.6,
    )
    assert reasons_for(rec) == []


def test_deduction_anomaly_does_not_duplicate_missing_deduction():
    """
    Both deduction rules can match the same record. Only the more specific
    reason — the one backed by component evidence — should be reported.
    """
    rec = record(
        prev_gross=60_000.0,
        curr_gross=60_000.0,
        prev_deductions=3_200.0,
        curr_deductions=2_400.0,
        deduction_delta=-800.0,
        net_delta_pct=1.4,
        missing_deduction_components=["Provident Fund"],
    )
    assert reasons_for(rec) == ["missing_deduction"]


# ---------------------------------------------------------------------------
# Rule interaction
# ---------------------------------------------------------------------------


def test_one_record_can_trigger_several_reasons():
    """Rules 3-6 are evaluated independently, not as a first-match chain."""
    rec = record(
        prev_net=40_000.0,
        curr_net=50_000.0,
        net_delta_pct=25.0,
        missing_deduction_components=["Professional Tax"],
    )
    assert reasons_for(rec) == ["large_net_change", "missing_deduction"]


# ---------------------------------------------------------------------------
# run() — filtering contract
# ---------------------------------------------------------------------------


def test_run_returns_only_the_flagged_records():
    records = [
        record(employee_id="E-1", employee_name="Clean One", net_delta_pct=2.0),
        record(employee_id="E-2", employee_name="Big Jump", net_delta_pct=40.0),
        record(employee_id="E-3", employee_name="Clean Two", net_delta_pct=-7.5),
        record(employee_id="E-4", employee_name="New Joiner", prev_net=None, curr_net=30_000.0),
    ]

    flagged = AnomalyDetectorAgent(threshold_pct=THRESHOLD).run(records)

    assert [f.comparison.employee_name for f in flagged] == ["Big Jump", "New Joiner"]


def test_run_on_clean_payroll_returns_nothing():
    """
    The empty result is what drives BRANCH A in the orchestrator — the
    CategorizationAgent is skipped entirely and no LLM call is made.
    """
    records = [record(employee_id=f"E-{i}", net_delta_pct=1.0) for i in range(5)]
    assert AnomalyDetectorAgent(threshold_pct=THRESHOLD).run(records) == []


def test_run_on_empty_input_returns_empty():
    assert AnomalyDetectorAgent(threshold_pct=THRESHOLD).run([]) == []


def test_record_with_no_payroll_figures_is_not_flagged():
    """
    Every comparison field is optional. Missing data must not be mistaken for
    an anomaly — the agent should stay silent rather than guess.
    """
    assert reasons_for(record()) == []


# ---------------------------------------------------------------------------
# summary_stats
# ---------------------------------------------------------------------------


def test_summary_stats_counts_each_reason():
    records = [
        record(employee_id="E-1", net_delta_pct=40.0),
        record(employee_id="E-2", net_delta_pct=25.0),
        record(employee_id="E-3", prev_net=None, curr_net=30_000.0),
        record(
            employee_id="E-4",
            net_delta_pct=30.0,
            missing_deduction_components=["Provident Fund"],
        ),
    ]

    agent = AnomalyDetectorAgent(threshold_pct=THRESHOLD)
    stats = agent.summary_stats(agent.run(records))

    assert stats == {
        "large_net_change": 3,
        "new_employee": 1,
        "missing_deduction": 1,
    }
