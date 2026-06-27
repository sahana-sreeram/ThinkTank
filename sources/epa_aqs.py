"""EPA Air Quality System (AQS) connector — annual PM2.5 by county.

https://aqs.epa.gov/aqsweb/documents/data_api.html

Requires free registration (email + key). Configure via env:
    EPA_AQS_EMAIL, EPA_AQS_KEY
Without both, the connector reports itself unavailable and is skipped — no error.

Returns a real annual PM2.5 summary for the request county as ``open_data``
evidence for emissions/air-quality arguments (e.g. congestion-pricing health
co-benefits). Geography-gated to Massachusetts in this demo build.
"""

from __future__ import annotations

import os
from typing import List, Optional

from models import EvidenceItem

from .base import Connector

AQS_ANNUAL = "https://aqs.epa.gov/data/api/annualData/byCounty"
PM25 = "88101"  # FRM/FEM PM2.5
_COUNTY_FIPS = {
    "boston": ("25", "025"),
    "suffolk": ("25", "025"),
    "massachusetts": ("25", "025"),
    "ma": ("25", "025"),
}


class EPAAQSConnector(Connector):
    id_prefix = "EPA-AQS"
    name = "EPA AQS"
    source_type = "government_report"

    def _fips(self, geography: Optional[str]):
        g = (geography or "").lower()
        for key, fips in _COUNTY_FIPS.items():
            if key in g:
                return fips
        return None

    def available(self) -> bool:
        return bool(os.getenv("EPA_AQS_EMAIL") and os.getenv("EPA_AQS_KEY"))

    def matches(self, geography: Optional[str]) -> bool:
        return self._fips(geography) is not None

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        from .base import http_get_json

        fips = self._fips(geography)
        if not fips:
            return []
        state, county = fips
        year = 2023
        data = http_get_json(
            AQS_ANNUAL,
            params={
                "email": os.getenv("EPA_AQS_EMAIL"),
                "key": os.getenv("EPA_AQS_KEY"),
                "param": PM25,
                "bdate": f"{year}0101",
                "edate": f"{year}1231",
                "state": state,
                "county": county,
            },
        )
        if not data or not isinstance(data, dict):
            return []
        rows = data.get("Data", []) or []
        # Prefer the annual arithmetic mean across monitors.
        means = [r.get("arithmetic_mean") for r in rows if r.get("arithmetic_mean") is not None]
        if not means:
            return []
        avg = sum(means) / len(means)
        text = (
            f"EPA AQS annual PM2.5 ({year}) for county FIPS {state}{county}: mean of "
            f"monitor annual arithmetic means = {avg:.1f} µg/m³ across {len(means)} "
            f"monitor-records. Source parameter 88101 (FRM/FEM PM2.5)."
        )
        return [
            self.make_item(
                local_id=f"pm25-{year}-{county}",
                title=f"Annual PM2.5 Air Quality {year} — FIPS {state}{county}",
                text=text,
                publication_date=str(year),
                geography=geography,
                target_geography=geography,
                relevance_score=0.75,
            )
        ]
