"""US Census American Community Survey (ACS) connector.

https://api.census.gov/data/2022/acs/acs5  ·  keyless for low volume; an optional
``CENSUS_API_KEY`` raises limits.

Returns real commute-mode counts for the request county as an ``open_data``
EvidenceItem. Every number traces to the Census table id in the text, satisfying
the policy-research numerical-claim rule (no fabricated numbers). Geography-gated:
only fires for Massachusetts / Boston requests in this demo build.
"""

from __future__ import annotations

import os
from typing import List, Optional

from models import EvidenceItem

from .base import Connector

ACS5 = "https://api.census.gov/data/2022/acs/acs5"

# Commuting to work (table B08301): total, drove alone, carpool, public transit,
# walked, worked from home.
_VARS = {
    "B08301_001E": "total commuters",
    "B08301_003E": "drove alone",
    "B08301_004E": "carpooled",
    "B08301_010E": "public transit",
    "B08301_019E": "walked",
    "B08301_021E": "worked from home",
}

# Minimal demo gazetteer: county FIPS for the geographies we support.
# Suffolk County = the city of Boston.
_COUNTY_FIPS = {
    "boston": ("25", "025"),
    "suffolk": ("25", "025"),
    "massachusetts": ("25", "025"),
    "ma": ("25", "025"),
}


class CensusACSConnector(Connector):
    id_prefix = "CENSUS-ACS"
    name = "US Census ACS"
    source_type = "open_data"

    def _resolve_fips(self, geography: Optional[str]):
        if not geography:
            return None
        g = geography.lower()
        for key, fips in _COUNTY_FIPS.items():
            if key in g:
                return fips
        return None

    def available(self) -> bool:
        # The ACS API now rejects keyless requests for these tables. The key is
        # free (api.census.gov/data/key_signup.html); without it we skip cleanly.
        return bool(os.getenv("CENSUS_API_KEY"))

    def matches(self, geography: Optional[str]) -> bool:
        return self._resolve_fips(geography) is not None

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        from .base import http_get_json

        fips = self._resolve_fips(geography)
        if not fips:
            return []
        state, county = fips
        params = {
            "get": "NAME," + ",".join(_VARS),
            "for": f"county:{county}",
            "in": f"state:{state}",
        }
        key = os.getenv("CENSUS_API_KEY")
        if key:
            params["key"] = key

        data = http_get_json(ACS5, params=params)
        # ACS returns [[header...],[row...]]
        if not data or not isinstance(data, list) or len(data) < 2:
            return []
        header, row = data[0], data[1]
        record = dict(zip(header, row))
        name = record.get("NAME", geography)

        def num(var: str) -> Optional[int]:
            try:
                return int(record[var])
            except (KeyError, TypeError, ValueError):
                return None

        total = num("B08301_001E")
        parts = []
        for var, label in _VARS.items():
            if var == "B08301_001E":
                continue
            v = num(var)
            if v is None:
                continue
            share = f" ({100 * v / total:.1f}%)" if total else ""
            parts.append(f"{label}: {v:,}{share}")
        if not parts:
            return []
        text = (
            f"American Community Survey (ACS 5-year, 2022) commute-to-work estimates "
            f"for {name} [Census table B08301]. Total commuters: "
            f"{total:,}. " + "; ".join(parts) + "."
        )
        return [
            self.make_item(
                local_id="B08301-2022-" + county,
                title=f"Commute Mode Share — {name} (ACS 2022)",
                text=text,
                publication_date="2022",
                geography=geography,
                target_geography=geography,
                relevance_score=0.8,
                url="https://data.census.gov/table?q=B08301&g=050XX00US" + state + county,
            )
        ]
