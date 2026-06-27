---
name: policy-evidence-retrieval
description: Retrieves and scores evidence for a policy research task from trusted
  government and academic sources. Use when any agent needs to find peer-reviewed
  papers, government datasets, or comparable policy case studies. Always use before
  synthesizing or making recommendations — never cite unsourced claims.
license: MIT
compatibility: Requires Python 3.11+, network access to OpenAlex and data.transportation.gov
metadata:
  author: thinktank-team
  version: "1.0"
---

# Policy Evidence Retrieval

Retrieves, scores, and normalizes evidence from trusted sources for use by specialist agents.

## When to Use
- Any agent needs citations before synthesizing findings
- Research Agent is populating its evidence corpus
- Stakeholder Agent needs comparable policy case studies

## Instructions

1. Extract 3-5 search queries from the agent task description
2. Query sources in priority order (see references/trusted-sources.md):
   - OpenAlex API for peer-reviewed papers
   - data.transportation.gov for federal datasets
   - MBTA Developer API for Boston-specific transit data
   - BTS (bts.gov) for national transportation statistics
3. Score each result using `source_scoring.py`:
   - credibility: 0.0-1.0 (peer-reviewed = 1.0, news = 0.3)
   - recency: 0.0-1.0 (published within 2 years = 1.0)
   - relevance: 0.0-1.0 (semantic match to task)
4. Discard results with combined score < 0.4
5. Normalize into the evidence schema below
6. Return top 5 results per query, deduplicated

## Output Schema

```json
{
  "evidence": [
    {
      "source": "string (publication or dataset name)",
      "url": "string",
      "credibility_score": 0.0,
      "recency_score": 0.0,
      "relevance_score": 0.0,
      "excerpt": "string (1-3 sentence summary)",
      "retrieved_by": "agent_name"
    }
  ]
}
```

## Gotchas

- OpenAlex rate limit: 10 req/sec without API key, 100/sec with. Always include the `mailto` param.
- Do not pass raw web search results as evidence — they must go through `source_scoring.py` first.
- If a source returns no results, widen the query before giving up.
- Never cite a source with credibility_score < 0.5 in the final recommendation.

## References
See [trusted-sources.md](references/trusted-sources.md) for the full source list with API endpoints.
