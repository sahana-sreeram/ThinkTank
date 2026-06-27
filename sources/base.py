"""Connector base class + shared HTTP helpers for the policy evidence sources.

OWNER: Person 2 (research/RAG).

Each external evidence source (OpenAlex, Semantic Scholar, MBTA, Census, EPA, …) is
a small `Connector` subclass that maps an API response into schema-valid
`EvidenceItem`s. Connectors are intentionally defensive: any network error, missing
API key, or unexpected payload results in an empty list and a logged warning — never
an exception that would break a policy run. The registry in ``sources/__init__.py``
fans queries out across all available connectors.

Design mirrors ``forecasters/``: drop in a new module, register it, done.
"""

from __future__ import annotations

import os
from typing import List, Optional

from logger import logger
from models import EvidenceItem, SourceType
from source_scoring import score_source

# Default per-connector network timeout (seconds). Kept short so a slow/blocked
# source degrades to "no evidence from this source" rather than stalling a run.
HTTP_TIMEOUT = float(os.getenv("POLICY_HTTP_TIMEOUT", "12"))
USER_AGENT = "PolicyThinkTank/0.1 (hackathon; mailto:team@example.org)"


def http_get_json(url: str, params: Optional[dict] = None, headers: Optional[dict] = None):
    """GET ``url`` and return parsed JSON, or ``None`` on any failure.

    requests is imported lazily so the module stays importable (and mock mode
    runnable) in environments without the dependency wired up.
    """
    try:
        import requests
    except ImportError:  # pragma: no cover - requests is a declared dependency
        logger.warning("requests not installed; cannot fetch %s", url)
        return None

    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    try:
        resp = requests.get(url, params=params, headers=merged, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001 - connectors must never raise upward
        logger.warning("source fetch failed (%s): %s", url, exc)
        return None


def clamp_text(text: str, limit: int = 1500) -> str:
    """Trim evidence text so a single chunk never dominates a briefing packet."""
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class Connector:
    """Base class for an evidence source.

    Subclasses set the class attributes and implement :meth:`fetch`. They may
    override :meth:`available` (e.g. to require an API key) and :meth:`matches`
    (e.g. to restrict to a geography or domain).
    """

    #: short stable prefix used to namespace ``source_id`` values, e.g. "OPENALEX"
    id_prefix: str = "SRC"
    #: display name for logs / UI
    name: str = "Source"
    #: the credibility tier this source maps to (see models.SourceType)
    source_type: SourceType = "other"

    def available(self) -> bool:
        """Whether the connector can run (deps present, key configured, …)."""
        return True

    def matches(self, geography: Optional[str]) -> bool:
        """Whether this source is relevant to the request. Default: always."""
        return True

    def fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- helpers for subclasses --------------------------------------------

    def make_item(
        self,
        *,
        local_id: str,
        title: str,
        text: str,
        organization: Optional[str] = None,
        publication_date: Optional[str] = None,
        geography: Optional[str] = None,
        target_geography: Optional[str] = None,
        relevance_score: float = 0.5,
        page: Optional[int] = None,
    ) -> EvidenceItem:
        """Build an :class:`EvidenceItem` with a deterministic credibility score.

        Credibility is computed by ``source_scoring.score_source`` from the source
        type, recency, and geography match — never invented by an LLM or a
        connector (see the policy-research skill's numerical-claim rule).
        """
        return EvidenceItem(
            source_id=f"{self.id_prefix}-{local_id}",
            title=title.strip() or "(untitled source)",
            organization=organization or self.name,
            source_type=self.source_type,
            publication_date=publication_date,
            geography=geography,
            page=page,
            text=clamp_text(text),
            relevance_score=round(max(0.0, min(1.0, relevance_score)), 3),
            credibility_score=score_source(
                self.source_type,
                publication_date=publication_date,
                geography=geography,
                target_geography=target_geography,
            ),
        )

    def safe_fetch(
        self, queries: List[str], geography: Optional[str], max_items: int
    ) -> List[EvidenceItem]:
        """Run :meth:`fetch` but swallow any error into an empty list + log."""
        if not self.available():
            logger.info("source %s unavailable (skipped)", self.name)
            return []
        if not self.matches(geography):
            return []
        try:
            items = self.fetch(queries, geography, max_items) or []
            logger.info("source %s returned %d items", self.name, len(items))
            return items
        except Exception as exc:  # noqa: BLE001
            logger.warning("source %s fetch raised: %s", self.name, exc)
            return []
