"""Socrata open-data discovery connector.

One connector covers every Socrata-hosted portal — US DOT (data.transportation.gov),
City of Boston (data.boston.gov), and others — via each portal's catalog discovery
API on its own host:

    https://<portal>/api/catalog/v1?q=...

This surfaces *real, relevant datasets* (name + description + last-updated) as
``open_data`` evidence the research agent can cite and a downstream analyst can pull.
No API key required; an optional Socrata app token raises rate limits.
"""

from __future__ import annotations

import os
from typing import List, Optional

from models import EvidenceItem

from .base import Connector

# Socrata-hosted portals. NOTE: data.boston.gov is CKAN/ArcGIS, not Socrata, so it
# is intentionally excluded here (a separate CKAN connector is the future home for
# City of Boston open data). data.transportation.gov (US DOT) is Socrata.
_FEDERAL_DOMAINS = ["data.transportation.gov"]
_BOSTON_DOMAINS: list[str] = []


class SocrataConnector(Connector):
    id_prefix = "SOCRATA"
    name = "Socrata Open Data"
    source_type = "open_data"

    def _domains(self, geography: Optional[str]) -> List[str]:
        domains = list(_FEDERAL_DOMAINS)
        g = (geography or "").lower()
        if any(k in g for k in ("boston", "massachusetts", "suffolk", " ma")):
            domains = _BOSTON_DOMAINS + domains
        return domains

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        from .base import http_get_json

        headers = {}
        token = os.getenv("SOCRATA_APP_TOKEN")
        if token:
            headers["X-App-Token"] = token

        domains = self._domains(geography)
        per_query = max(1, max_items // (max(1, len(queries)) * len(domains)))
        items: list[EvidenceItem] = []
        seen: set[str] = set()
        for domain in domains:
            catalog = f"https://{domain}/api/catalog/v1"
            for query in queries:
                data = http_get_json(
                    catalog,
                    params={"q": query, "only": "dataset", "limit": per_query},
                    headers=headers,
                )
                if not data:
                    continue
                results = data.get("results", []) if isinstance(data, dict) else []
                n = len(results)
                for rank, entry in enumerate(results):
                    resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
                    rid = resource.get("id")
                    name = resource.get("name") or ""
                    desc = resource.get("description") or ""
                    if not rid or rid in seen or not name:
                        continue
                    seen.add(rid)
                    updated = (resource.get("updatedAt") or "")[:10] or None
                    permalink = entry.get("permalink") or entry.get("link") or ""
                    text = (
                        f"Open dataset '{name}' from {domain}. "
                        f"{desc} Access: {permalink}".strip()
                    )
                    rel = 0.75 - 0.35 * (rank / n) if n else 0.5
                    items.append(
                        self.make_item(
                            local_id=rid,
                            title=name,
                            text=text,
                            organization=domain,
                            publication_date=updated,
                            geography=geography if domain == "data.boston.gov" else None,
                            target_geography=geography,
                            relevance_score=rel,
                        )
                    )
        return items
