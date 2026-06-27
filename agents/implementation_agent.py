"""Policy implementation & recommendation agent.

OWNER: Person 3 (impl/forecast/evals). Synthesizes stakeholder findings, analyzes
feasibility, compares alternatives, and produces a recommendation with a phased
implementation plan and success metrics.

Public functions (frozen):
    synthesize_research(request, research) -> ResearchSynthesis
    create_policy_recommendation(request, research) -> PolicyRecommendation
"""

from __future__ import annotations

from config import MOCK_MODE
from models import (
    Finding,
    ImpactAnalysis,
    ImplementationPlan,
    ImplementationStep,
    PolicyAlternative,
    PolicyRecommendation,
    PolicyRequest,
    ResearchSynthesis,
    StakeholderResearchResult,
)


def synthesize_research(
    request: PolicyRequest,
    research: list[StakeholderResearchResult],
) -> ResearchSynthesis:
    """Combine stakeholder findings into a cross-cutting synthesis."""
    if not MOCK_MODE:
        raise NotImplementedError("Real synthesize_research not implemented yet (P3).")

    all_findings: list[Finding] = [f for r in research for f in r.findings]
    evidence_ids = sorted({eid for f in all_findings for eid in f.evidence_ids})
    data_gaps = sorted({g for r in research for g in r.data_gaps})
    positions = [r.likely_position for r in research]

    return ResearchSynthesis(
        summary=f"Across {len(research)} stakeholder perspectives, there is qualified "
        f"support for action on '{request.question}', contingent on equity safeguards.",
        consensus_points=[
            "Some intervention is justified by the evidence.",
            "Mitigations are required to protect vulnerable groups.",
        ],
        disagreements=[
            "Stakeholders differ on the acceptable level of commuter cost.",
        ],
        key_findings=all_findings[:5],
        evidence_ids=evidence_ids,
        data_gaps=data_gaps,
    )


def create_policy_recommendation(
    request: PolicyRequest,
    research: list[StakeholderResearchResult],
) -> PolicyRecommendation:
    """Produce a recommendation, alternatives, and a phased implementation plan."""
    if not MOCK_MODE:
        raise NotImplementedError(
            "Real create_policy_recommendation not implemented yet (P3)."
        )

    evidence_ids = sorted(
        {eid for r in research for f in r.findings for eid in f.evidence_ids}
    )
    topic = request.question.rstrip("?")
    plan = ImplementationPlan(
        steps=[
            ImplementationStep(
                phase="Phase 1: Design & Authorization",
                actions=[
                    "Confirm legal authority and finalize the policy design",
                    "Define eligibility, scope, and protective carve-outs",
                ],
                timeline="Months 0-6",
                owner="Lead agency",
            ),
            ImplementationStep(
                phase="Phase 2: Pilot & Build",
                actions=[
                    "Stand up the operational and data infrastructure",
                    "Run a limited pilot with monitoring and feedback",
                ],
                timeline="Months 6-18",
                owner="Lead agency + delivery partners",
            ),
            ImplementationStep(
                phase="Phase 3: Rollout & Reinvestment",
                actions=[
                    "Scale based on pilot results",
                    "Direct gains toward affected and underserved groups",
                ],
                timeline="Months 18-36",
                owner="Oversight body",
            ),
        ],
        success_metrics=[
            "Measurable progress toward the stated objective vs. baseline",
            "Costs remain within the stated constraints",
            "No net harm to the most affected groups",
        ],
        monitoring=[
            "Quarterly outcome reporting against the success metrics",
            "Annual equity-impact audit",
        ],
    )

    return PolicyRecommendation(
        summary=f"Adopt a phased, equity-protected approach to '{topic}' in "
        f"{request.geography}, piloted before full rollout and monitored against "
        f"clear success metrics.",
        recommended_actions=[
            f"Implement the core intervention addressing: {topic}",
            "Add targeted protections for the most affected groups",
            "Direct benefits/savings toward equity and reinvestment",
        ],
        alternatives=["No action", "A narrower / lower-cost variant", "A phased pilot only"],
        benefits=[
            "Direct progress on the stated objective",
            "A dedicated mechanism to fund follow-through",
            "Reduced long-term costs of inaction",
        ],
        risks=[
            "Regressive impact if protections are poorly designed",
            "Displacement or spillover of the problem to nearby groups",
        ],
        equity_effects=[
            "Vulnerable groups could be disproportionately burdened without safeguards",
            "Targeted reinvestment can offset burden if directed to underserved groups",
        ],
        evidence_ids=evidence_ids,
        confidence=0.7,
        impact=ImpactAnalysis(
            economic="Net positive if benefits are realized; transition costs for some groups.",
            equity="Risk of regressivity, mitigable via safeguards and targeted reinvestment.",
            political="Contested; visible safeguards and reinvestment build support.",
            operational="Feasible with established delivery mechanisms.",
            legal="Requires confirmation of authorizing authority.",
        ),
        implementation_plan=plan,
        alternatives_detail=[
            PolicyAlternative(
                name="No action",
                description="Maintain the status quo.",
                pros=["No implementation cost", "No political friction"],
                cons=["The underlying problem persists", "No new capacity to act"],
            ),
            PolicyAlternative(
                name="Narrower variant",
                description="A smaller-scope, lower-cost version of the intervention.",
                pros=["Lower cost and risk", "Faster to deliver"],
                cons=["Weaker effect on the objective", "May not reach key groups"],
            ),
        ],
    )
