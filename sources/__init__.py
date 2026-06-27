"""Evidence source connector registry (OWNER: Person 2).

Fans a set of research queries out across every available external source and
returns merged, schema-valid ``EvidenceItem``s. Connectors that are unavailable
(missing key/deps) or irrelevant (geography/domain mismatch) are skipped silently;
none can raise into a policy run (see ``Connector.safe_fetch``).

Add a source by writing a ``Connector`` subclass and appending it to ``_REGISTRY``.
"""

from __future__ import annotations

from typing import List, Optional

from logger import logger
from models import EvidenceItem

from .base import Connector
from .census import CensusACSConnector
from .epa_aqs import EPAAQSConnector
from .mbta import MBTAConnector
from .openalex import OpenAlexConnector
from .semantic_scholar import SemanticScholarConnector
from .socrata import SocrataConnector

# Order is a mild preference hint only; final ranking is by relevance*credibility.
_REGISTRY: List[Connector] = [
    OpenAlexConnector(),
    SemanticScholarConnector(),
    CensusACSConnector(),
    SocrataConnector(),
    MBTAConnector(),
    EPAAQSConnector(),
]

# Map each connector's source_type so callers can pre-filter by source_types.
def _matches_types(conn: Connector, source_types: Optional[List[str]]) -> bool:
    return not source_types or conn.source_type in source_types


def available_sources() -> List[str]:
    """Names of connectors that can currently run (for UI/observability)."""
    return [c.name for c in _REGISTRY if c.available()]


def fetch_evidence(
    queries: List[str],
    geography: Optional[str] = None,
    source_types: Optional[List[str]] = None,
    max_items: int = 18,
) -> List[EvidenceItem]:
    """Fetch evidence across all matching, available connectors.

    ``max_items`` is a soft global budget; it is divided across connectors so a
    single source cannot dominate. De-duplication and final ranking happen in
    ``retrieval.retrieve_policy_evidence``.
    """
    if not queries:
        return []
    active = [
        c
        for c in _REGISTRY
        if _matches_types(c, source_types) and c.available() and c.matches(geography)
    ]
    if not active:
        logger.info("no active evidence connectors for this request")
        return []
    per_source = max(2, max_items // len(active))
    collected: list[EvidenceItem] = []
    for conn in active:
        collected.extend(conn.safe_fetch(queries, geography, per_source))
    logger.info(
        "fetch_evidence: %d items from %d connectors", len(collected), len(active)
    )
    return collected
