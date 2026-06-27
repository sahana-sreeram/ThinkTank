"""Agent package for the Policy Think Tank.

Four logical roles, each in its own module with a stable public function:
  - policy_director      (P1): plan_policy, revise_recommendation
  - stakeholder_research (P2): run_stakeholder_research
  - implementation_agent (P3): synthesize_research, create_policy_recommendation
  - red_team_agent       (P3): red_team_review  (domain-neutral)

All ship MOCK implementations (config.MOCK_MODE) so the four workstreams can
develop in parallel before any real model wiring exists.
"""

from agents.implementation_agent import create_policy_recommendation, synthesize_research
from agents.policy_director import plan_policy, revise_recommendation
from agents.red_team_agent import red_team_review
from agents.stakeholder_research import run_stakeholder_research

__all__ = [
    "plan_policy",
    "revise_recommendation",
    "run_stakeholder_research",
    "synthesize_research",
    "create_policy_recommendation",
    "red_team_review",
]
