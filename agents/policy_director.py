"""Policy Director agent.

OWNER: Person 1 (orchestration). Interprets the request into a structured
objective, defines the stakeholder roster + research tasks, and revises the
recommendation when the Red Team demands it.

Foundation version is MOCK: it returns schema-valid objects without calling a
model. Real version will build a local agent (agent_builder) with a compact
BriefingPacket and structured-output validation.
"""

from __future__ import annotations

from config import MOCK_MODE
from models import (
    CritiqueResult,
    PolicyObjective,
    PolicyRecommendation,
    PolicyRequest,
    PolicyTask,
    StakeholderProfile,
)

# Default domain-neutral stakeholder roster. These lenses apply to any policy
# question; a future Director can tailor or add domain-specific perspectives.
_DEFAULT_STAKEHOLDERS = [
    StakeholderProfile(
        key="government_regulatory",
        name="Government & Regulatory",
        perspective="Legal authority, fiscal responsibility, and regulatory feasibility.",
        priorities=["legal authority", "budget", "enforceability"],
        skills=["policy-research"],
    ),
    StakeholderProfile(
        key="community_equity",
        name="Community & Equity",
        perspective="Distributional fairness and impact on vulnerable populations.",
        priorities=["equity", "affordability", "access"],
        skills=["policy-research"],
    ),
    StakeholderProfile(
        key="economic_fiscal",
        name="Economic & Fiscal",
        perspective="Effects on the economy, employment, costs, and public finances.",
        priorities=["economic impact", "cost", "competitiveness"],
        skills=["policy-research"],
    ),
    StakeholderProfile(
        key="subject_matter_expert",
        name="Subject-Matter & Implementation Expert",
        perspective="Technical evidence and operational feasibility for this issue.",
        priorities=["evidence base", "operational feasibility", "unintended effects"],
        skills=["policy-research"],
    ),
]


def plan_policy(
    request: PolicyRequest,
) -> tuple[PolicyObjective, list[StakeholderProfile], list[PolicyTask]]:
    """Define objective + success criteria, pick stakeholders, and delegate tasks."""
    if not MOCK_MODE:
        # TODO(P1): real Policy Director call via agent_builder with structured output.
        raise NotImplementedError("Real policy_director not implemented yet (P1).")

    objective = PolicyObjective(
        statement=request.objective or f"Evaluate: {request.question}",
        success_metrics=[
            "Measurable progress toward the stated objective",
            "Costs justified by benefits, within the stated constraints",
            "No disproportionate burden on vulnerable or affected groups",
        ],
        constraints=list(request.constraints),
        out_of_scope=["Issues outside the stated geography or objective"],
    )

    stakeholders = list(_DEFAULT_STAKEHOLDERS)
    tasks = [
        PolicyTask(
            task_id=f"task_{s.key}",
            description=f"Research {request.question} from the {s.name} perspective.",
            stakeholder_key=s.key,
            queries=[
                f"{request.question} {p} {request.geography}" for p in s.priorities
            ],
            required_outputs=["cited findings", "likely position", "concerns"],
        )
        for s in stakeholders
    ]
    return objective, stakeholders, tasks


def revise_recommendation(
    request: PolicyRequest,
    recommendation: PolicyRecommendation,
    critique: CritiqueResult,
) -> PolicyRecommendation:
    """Apply the Red Team's required revisions to the recommendation."""
    if not MOCK_MODE:
        # TODO(P1): real revision call incorporating critique.required_revisions.
        raise NotImplementedError("Real revise_recommendation not implemented yet (P1).")

    revised = recommendation.model_copy(deep=True)
    revised.summary = "[Revised after red-team review] " + recommendation.summary
    # Fold each required revision into actions/risks so the change is visible.
    for fix in critique.required_revisions:
        revised.recommended_actions.append(f"Address red-team concern: {fix}")
    for consequence in critique.unintended_consequences:
        if consequence not in revised.risks:
            revised.risks.append(consequence)
    revised.confidence = max(0.0, recommendation.confidence - 0.1)
    return revised
