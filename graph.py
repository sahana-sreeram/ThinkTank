r"""LangGraph state graph for the policy workflow.

OWNER: Person 1 (orchestration). Wires the orchestrator node functions into the
graph below. A pure-Python fallback executor mirrors the same topology so the
workflow runs even if langgraph is unavailable (e.g. minimal CI).

    START
      -> plan_policy            (objective + stakeholders + skill-assigned tasks)
      -> research               (objective cited evidence)
      -> stakeholder_research   (per-perspective; cited findings)
      -> synthesize_research
      -> implementation_and_recommendation
      -> run_forecast
      -> finalize_result
      -> END
"""

from __future__ import annotations

from typing import Any

from orchestrator import (
    PolicyState,
    node_finalize,
    node_forecast,
    node_plan_policy,
    node_recommend,
    node_research,
    node_stakeholder_research,
    node_synthesize,
)


def build_graph():
    """Build and compile the LangGraph StateGraph. Raises if langgraph missing."""
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(dict)

    builder.add_node("plan_policy", node_plan_policy)
    builder.add_node("research", node_research)
    builder.add_node("stakeholder_research", node_stakeholder_research)
    builder.add_node("synthesize_research", node_synthesize)
    builder.add_node("implementation_and_recommendation", node_recommend)
    builder.add_node("run_forecast", node_forecast)
    builder.add_node("finalize_result", node_finalize)

    builder.add_edge(START, "plan_policy")
    builder.add_edge("plan_policy", "research")
    builder.add_edge("research", "stakeholder_research")
    builder.add_edge("stakeholder_research", "synthesize_research")
    builder.add_edge("synthesize_research", "implementation_and_recommendation")
    builder.add_edge("implementation_and_recommendation", "run_forecast")
    builder.add_edge("run_forecast", "finalize_result")
    builder.add_edge("finalize_result", END)

    return builder.compile()


def _run_fallback(state: PolicyState) -> PolicyState:
    """Sequential executor mirroring the graph topology (no langgraph required)."""
    node_plan_policy(state)
    node_research(state)
    node_stakeholder_research(state)
    node_synthesize(state)
    node_recommend(state)
    node_forecast(state)
    node_finalize(state)
    return state


def run_graph(state: PolicyState) -> dict[str, Any]:
    """Execute the workflow, preferring LangGraph and falling back if unavailable."""
    try:
        graph = build_graph()
    except Exception:
        return _run_fallback(state)

    # The compiled graph mutates/returns the shared dict state. A recursion limit
    # generously covers the bounded revision loop.
    return graph.invoke(state, config={"recursion_limit": 50})
