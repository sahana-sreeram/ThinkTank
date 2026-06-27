"""Stakeholder research agent system.

OWNER: Person 2 (research/RAG). One shared agent implementation, dynamically
configured into different policy perspectives. Each retrieves evidence and returns
cited findings, likely position, concerns, mitigations, and data gaps.

Public function (frozen, must work without Streamlit/LangGraph):
    run_stakeholder_research(request, tasks, stakeholders) -> list[StakeholderResearchResult]
"""

from __future__ import annotations

from config import DEFAULT_TOP_K, MOCK_MODE
from models import (
    Finding,
    PolicyRequest,
    PolicyTask,
    StakeholderProfile,
    StakeholderResearchResult,
)
from retrieval import retrieve_policy_evidence


def _mock_result(
    request: PolicyRequest,
    task: PolicyTask,
    profile: StakeholderProfile,
) -> StakeholderResearchResult:
    evidence = retrieve_policy_evidence(
        task.queries, geography=request.geography, top_k=DEFAULT_TOP_K
    )
    evidence_ids = [e.source_id for e in evidence]
    findings = [
        Finding(
            claim=f"From the {profile.name} view, {request.question.rstrip('?')} "
            f"primarily affects {profile.priorities[0]}.",
            evidence_ids=evidence_ids[:2],
            confidence=0.7,
            assumptions=[f"Local conditions resemble those in source {evidence_ids[0]}."]
            if evidence_ids
            else ["No local evidence available; reasoning by analogy."],
            limitations=["Limited city-specific data in the curated corpus."],
        ),
    ]
    return StakeholderResearchResult(
        stakeholder=profile.name,
        findings=findings,
        likely_position=f"{profile.name} is cautiously supportive if {profile.priorities[0]} "
        "concerns are addressed.",
        concerns=[f"Potential negative impact on {p}" for p in profile.priorities[1:]],
        proposed_mitigations=[f"Targeted measures to protect {profile.priorities[-1]}"],
        data_gaps=[f"Need recent {request.geography} data on {profile.priorities[0]}"],
        handoff_summary=f"{profile.name}: cautiously supportive; key concern = "
        f"{profile.priorities[-1]}; {len(evidence_ids)} sources cited.",
    )


def run_stakeholder_research(
    request: PolicyRequest,
    tasks: list[PolicyTask],
    stakeholders: list[StakeholderProfile],
) -> list[StakeholderResearchResult]:
    """Run each stakeholder's research task and return cited results.

    Independent of Streamlit and LangGraph by contract. Foundation version is MOCK
    (fixture-backed retrieval); P2 will wire the shared agent + real RAG.
    """
    if not MOCK_MODE:
        # TODO(P2): real shared agent per stakeholder with skill-loaded briefing
        # packet, structured-output validation, and credibility-ranked evidence.
        raise NotImplementedError("Real stakeholder research not implemented yet (P2).")

    by_key = {s.key: s for s in stakeholders}
    results = []
    for task in tasks:
        profile = by_key.get(task.stakeholder_key)
        if profile is None:
            continue
        results.append(_mock_result(request, task, profile))
    return results
