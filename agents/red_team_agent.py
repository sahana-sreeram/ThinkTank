"""Red-Team agent.

OWNER: Person 3 (impl/forecast/evals). Challenges the recommendation for weak
claims, unintended consequences, missing perspectives, and equity blind spots, and
decides whether a revision is required.

Forecast parameter derivation is NOT here — it belongs to the matched domain module
(see `forecasters/`), because it is domain-specific. The Red Team is domain-neutral.

Public function (frozen):
    red_team_review(request, recommendation) -> CritiqueResult
"""

from __future__ import annotations

from config import MOCK_MODE
from models import CritiqueResult, PolicyRecommendation, PolicyRequest


def red_team_review(
    request: PolicyRequest,
    recommendation: PolicyRecommendation,
) -> CritiqueResult:
    """Challenge the recommendation for weak claims, risks, and gaps."""
    if not MOCK_MODE:
        raise NotImplementedError("Real red_team_review not implemented yet (P3).")

    unsupported = [
        action
        for action in recommendation.recommended_actions
        if not recommendation.evidence_ids
    ]
    # Severity is high on the first pass if equity effects aren't concretely addressed.
    has_equity = bool(recommendation.equity_effects)
    severity = "high" if not has_equity else "medium"

    return CritiqueResult(
        issues=[
            "Key projections rest on assumptions that are not yet validated for "
            f"{request.geography}.",
            "Second-order and displacement effects are acknowledged but not quantified.",
        ],
        unsupported_claims=unsupported
        or ["Stated confidence level lacks an accompanying sensitivity analysis."],
        unintended_consequences=[
            "Effects may spill over to adjacent populations or jurisdictions.",
            "Affected groups may adapt in ways that erode the intended benefit.",
        ],
        missing_perspectives=[
            "Frontline implementers / operators",
            "Groups most exposed to the downside risks",
        ],
        required_revisions=[
            "Add a concrete equity-protection mechanism before rollout"
            if not has_equity
            else "Define monitoring triggers for the identified second-order effects",
        ],
        severity=severity,
    )
