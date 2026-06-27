"""End-to-end mock workflow tests for the orchestrator + graph."""

from models import PolicyRequest, PolicyRunResult

REQ = PolicyRequest(
    question="Should Boston implement congestion pricing downtown?",
    geography="Boston, MA",
    objective="Reduce downtown congestion while protecting equity",
    constraints=["Protect low-income commuters"],
    timeline="3 years",
)


def test_end_to_end_produces_complete_result():
    from orchestrator import run_policy_analysis

    res = run_policy_analysis(REQ)
    assert isinstance(res, PolicyRunResult)
    assert res.objective is not None
    assert len(res.stakeholders) >= 3  # multiple perspectives
    # stakeholder results match the stakeholder-typed tasks; research briefs come
    # from the research-typed tasks the Director also created.
    stakeholder_tasks = [t for t in res.tasks if t.agent_type == "stakeholder"]
    assert len(res.research) == len(stakeholder_tasks)
    assert len(res.research_briefs) >= 1
    assert all(t.skills for t in res.tasks)  # Director assigned skills to every task
    assert res.synthesis is not None
    assert res.recommendation is not None
    assert res.forecast is not None
    assert res.model_events  # model calls were logged
    assert res.events  # human-readable activity log populated


def test_no_red_team_or_revision_in_flow():
    from orchestrator import run_policy_analysis

    res = run_policy_analysis(REQ)
    # The red-team agent and revision loop were removed; the result model no longer
    # carries critiques/revisions, and the event log mentions neither.
    assert not hasattr(res, "critiques")
    assert not hasattr(res, "revisions")
    joined = " ".join(res.events).lower()
    assert "red team" not in joined and "revis" not in joined


def test_fallback_executor_matches_topology():
    from graph import _run_fallback

    state = {
        "run_id": "t",
        "request": REQ,
        "model_events": [],
        "events": [],
    }
    out = _run_fallback(state)
    assert out["recommendation"] is not None and out["forecast"] is not None
