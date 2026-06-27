"""OpenAlex connector — free, no API key, 250M+ scholarly works.

https://docs.openalex.org/  ·  GET https://api.openalex.org/works?search=...

Maps each work to an ``academic`` EvidenceItem. Abstracts arrive as an inverted
index (token -> positions); we reconstruct readable text from it.
"""

from __future__ import annotations

from typing import List, Optional

from models import EvidenceItem

from .base import Connector

OPENALEX_WORKS = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """Rebuild abstract text from OpenAlex's {token: [positions]} index."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for token, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, token))
    positions.sort(key=lambda p: p[0])
    return " ".join(tok for _, tok in positions)


class OpenAlexConnector(Connector):
    id_prefix = "OPENALEX"
    name = "OpenAlex"
    source_type = "academic"

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        from .base import http_get_json

        per_query = max(1, max_items // max(1, len(queries)))
        items: list[EvidenceItem] = []
        seen: set[str] = set()
        for query in queries:
            data = http_get_json(
                OPENALEX_WORKS,
                params={
                    "search": query,
                    "per-page": per_query,
                    "mailto": "team@example.org",
                    # Prefer works with an abstract and reasonable citation count.
                    "sort": "relevance_score:desc",
                },
            )
            if not data:
                continue
            results = data.get("results", []) if isinstance(data, dict) else []
            n = len(results)
            for rank, work in enumerate(results):
                oid = (work.get("id") or "").rsplit("/", 1)[-1]
                if not oid or oid in seen:
                    continue
                seen.add(oid)
                abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
                title = work.get("display_name") or work.get("title") or ""
                if not (abstract or title):
                    continue
                org = None
                loc = work.get("primary_location") or {}
                src = (loc.get("source") or {}) if isinstance(loc, dict) else {}
                if isinstance(src, dict):
                    org = src.get("display_name")
                year = work.get("publication_year")
                # Prefer the DOI link, then the journal landing page, then OpenAlex.
                doi = work.get("doi")
                landing = loc.get("landing_page_url") if isinstance(loc, dict) else None
                url = doi or landing or work.get("id")
                # API relevance descends with rank within a query.
                rel = 0.9 - 0.5 * (rank / n) if n else 0.6
                items.append(
                    self.make_item(
                        local_id=oid,
                        title=title,
                        text=abstract or title,
                        organization=org or "OpenAlex indexed venue",
                        publication_date=str(year) if year else None,
                        geography=None,  # papers are not geography-bound
                        target_geography=geography,
                        relevance_score=rel,
                        url=url,
                    )
                )
        return items
