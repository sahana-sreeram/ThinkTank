"""Live smoke test for the P2 evidence connectors (hits real APIs — needs network).

Usage:
    python tools/fetch_sources_smoke.py
    python tools/fetch_sources_smoke.py "Should Seattle add a downtown cordon toll?" "Seattle, WA"

Prints which connectors are available, then fetches and ranks live evidence so you
can eyeball real titles/sources. Does NOT require Ollama (no embedding/caching here).
Set API keys (CENSUS_API_KEY, MBTA_API_KEY, EPA_AQS_EMAIL/EPA_AQS_KEY) to light up
the geography-gated structured sources.
"""

import os
import sys

# Allow running as `python tools/fetch_sources_smoke.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sources  # noqa: E402


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "Should Boston implement congestion pricing downtown?"
    geography = sys.argv[2] if len(sys.argv) > 2 else "Boston, MA"
    queries = [
        "congestion pricing traffic reduction outcomes",
        "cordon pricing equity impact low-income commuters",
        "congestion charge transit ridership revenue",
    ]
    print(f"Question : {question}")
    print(f"Geography: {geography}")
    print(f"Available connectors: {sources.available_sources()}\n")

    items = sources.fetch_evidence(queries, geography=geography, max_items=24)
    items.sort(key=lambda e: e.relevance_score * e.credibility_score, reverse=True)
    print(f"\n=== {len(items)} evidence items (ranked) ===\n")
    for it in items:
        print(
            f"[{it.source_type:16s}] r={it.relevance_score:.2f} "
            f"c={it.credibility_score:.2f}  {it.source_id}"
        )
        print(f"    {it.title[:100]}")
        print(f"    org={it.organization}  date={it.publication_date}")
        print(f"    {it.text[:160]}...\n")


if __name__ == "__main__":
    main()
