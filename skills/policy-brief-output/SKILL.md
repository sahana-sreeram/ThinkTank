---
name: policy-brief-output
description: Formats a completed policy analysis into a structured executive brief
  with confidence scores, equity analysis, and scenario forecasts. Use when the
  Policy Director is ready to produce the final deliverable. Always use this skill
  for final output — never produce a freeform summary in its place.
license: MIT
metadata:
  author: thinktank-team
  version: "1.0"
---

# Policy Brief Output

Enforces a consistent, judge-readable output format for the final policy recommendation.

## When to Use
- Policy Director is producing the final recommendation
- After red team critique and revision are complete
- Before the Forecasting Agent runs scenarios

## Instructions

1. Populate each section of the brief template (see assets/brief-template.md)
2. Confidence score = average of all agent confidence scores, weighted by evidence count
3. Include at minimum 2 dissenting stakeholder perspectives in the Equity section
4. Forecast scenarios must come from `forecasting.py` — never generate numbers from the LLM
5. Flag any claim with credibility_score < 0.6 with a ⚠️ marker

## Gotchas

- Never omit the Confidence & Assumptions section — this is what separates a policy brief from an opinion.
- Forecast numbers must be sourced from deterministic Python, not LLM generation.
- If fewer than 3 evidence sources back a recommendation, downgrade confidence to LOW.
- Equity section must name specific affected groups, not generic "vulnerable populations".

## Output Template

See [brief-template.md](assets/brief-template.md) for the full section structure.
