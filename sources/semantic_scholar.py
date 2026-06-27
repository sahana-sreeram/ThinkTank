"""Semantic Scholar connector — free, no key required (rate-limited).

https://api.semanticscholar.org/graph/v1/paper/search?query=...

Maps each paper to an ``academic`` EvidenceItem. An optional API key
(``SEMANTIC_SCHOLAR_API_KEY``) raises the rate limit but is not required.
"""

from __future__ import annotations

import os
from typing import List, Optional

from models import EvidenceItem

from .base import Connector

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,year,venue,externalIds,citationCount,url"


class SemanticScholarConnector(Connector):
    id_prefix = "S2"
    name = "Semantic Scholar"
    source_type = "academic"

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        from .base import http_get_json

        headers = {}
        key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        if key:
            headers["x-api-key"] = key

        per_query = max(1, max_items // max(1, len(queries)))
        items: list[EvidenceItem] = []
        seen: set[str] = set()
        for query in queries:
            data = http_get_json(
                S2_SEARCH,
                params={"query": query, "limit": per_query, "fields": _FIELDS},
                headers=headers,
            )
            if not data:
                continue
            papers = data.get("data", []) if isinstance(data, dict) else []
            n = len(papers)
            for rank, paper in enumerate(papers):
                pid = paper.get("paperId")
                abstract = paper.get("abstract")
                title = paper.get("title") or ""
                if not pid or pid in seen:
                    continue
                if not (abstract or title):
                    continue
                seen.add(pid)
                year = paper.get("year")
                rel = 0.9 - 0.5 * (rank / n) if n else 0.6
                items.append(
                    self.make_item(
                        local_id=pid[:24],
                        title=title,
                        text=abstract or title,
                        organization=paper.get("venue") or "Semantic Scholar indexed venue",
                        publication_date=str(year) if year else None,
                        target_geography=geography,
                        relevance_score=rel,
                    )
                )
        return items
