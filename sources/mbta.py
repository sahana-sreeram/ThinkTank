"""MBTA v3 API connector — Boston transit system state.

https://api-v3.mbta.com/  ·  works without a key at a low rate limit; an optional
``MBTA_API_KEY`` raises it.

Returns a current snapshot of subway/light-rail service alerts as ``open_data``
evidence about transit reliability — directly relevant to congestion-pricing and
transit-investment questions. Geography-gated to Boston / Massachusetts.
"""

from __future__ import annotations

import os
from typing import List, Optional

from models import EvidenceItem

from .base import Connector

MBTA_ALERTS = "https://api-v3.mbta.com/alerts"


class MBTAConnector(Connector):
    id_prefix = "MBTA"
    name = "MBTA v3 API"
    source_type = "open_data"

    def matches(self, geography: Optional[str]) -> bool:
        g = (geography or "").lower()
        return any(k in g for k in ("boston", "massachusetts", "suffolk", " ma", "mbta"))

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        from .base import http_get_json
        from datetime import date

        headers = {}
        key = os.getenv("MBTA_API_KEY")
        if key:
            headers["x-api-key"] = key

        data = http_get_json(
            MBTA_ALERTS,
            params={
                # route_type 0 = light rail (Green), 1 = subway (Red/Orange/Blue)
                "filter[route_type]": "0,1",
                "page[limit]": 25,
            },
            headers=headers,
        )
        if not data or not isinstance(data, dict):
            return []
        alerts = data.get("data", [])
        if not alerts:
            return []

        by_effect: dict[str, int] = {}
        headlines: list[str] = []
        for alert in alerts:
            attrs = alert.get("attributes", {}) if isinstance(alert, dict) else {}
            effect = attrs.get("effect", "UNKNOWN")
            by_effect[effect] = by_effect.get(effect, 0) + 1
            short = attrs.get("short_header") or attrs.get("header")
            if short and len(headlines) < 5:
                headlines.append(short)

        summary = "; ".join(f"{v} {k.lower().replace('_', ' ')}" for k, v in by_effect.items())
        text = (
            f"MBTA rapid-transit (subway + light rail) had {len(alerts)} active service "
            f"alerts as of {date.today().isoformat()}: {summary}. "
            f"Examples: {' | '.join(headlines)}."
        )
        return [
            self.make_item(
                local_id="alerts-" + date.today().isoformat(),
                title="MBTA Rapid Transit Service Alerts (current snapshot)",
                text=text,
                publication_date=date.today().isoformat(),
                geography=geography or "Boston, MA",
                target_geography=geography,
                relevance_score=0.7,
            )
        ]
