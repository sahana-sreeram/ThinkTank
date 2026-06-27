"""Tests for the P2 evidence-source layer: connectors, registry, cache, hybrid.

All network and embeddings are faked, so these run offline and deterministically.
"""

from __future__ import annotations

import hashlib

import pytest

import config
import retrieval
import sources
from evidence_cache import EvidenceCache
from models import EvidenceItem


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
def _fake_embedder(dim: int = 64):
    """Deterministic bag-of-words hashing embedder (no Ollama needed)."""

    def embed(texts):
        vecs = []
        for t in texts:
            v = [0.0] * dim
            for tok in t.lower().split():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % dim] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            vecs.append([x / norm for x in v])
        return vecs

    return embed


OPENALEX_PAYLOAD = {
    "results": [
        {
            "id": "https://openalex.org/W123",
            "display_name": "Congestion Pricing Outcomes in Cities",
            "publication_year": 2021,
            "abstract_inverted_index": {"Congestion": [0], "pricing": [1], "works": [2]},
            "primary_location": {"source": {"display_name": "J. Transport Econ"}},
        }
    ]
}


# --------------------------------------------------------------------------- #
# Connector mapping
# --------------------------------------------------------------------------- #
def test_openalex_maps_to_valid_evidence(monkeypatch):
    from sources import openalex

    monkeypatch.setattr(openalex, "http_get_json", lambda *a, **k: OPENALEX_PAYLOAD, raising=False)
    # http_get_json is imported inside fetch via `from .base import http_get_json`,
    # so patch it on base.
    import sources.base as base

    monkeypatch.setattr(base, "http_get_json", lambda *a, **k: OPENALEX_PAYLOAD)

    items = openalex.OpenAlexConnector().fetch(["congestion pricing"], "Boston, MA", 6)
    assert items and all(isinstance(i, EvidenceItem) for i in items)
    it = items[0]
    assert it.source_id == "OPENALEX-W123"
    assert it.source_type == "academic"
    assert it.text == "Congestion pricing works"  # reconstructed from inverted index
    assert 0.0 <= it.credibility_score <= 1.0
    assert 0.0 <= it.relevance_score <= 1.0


def test_connector_never_raises_on_bad_payload(monkeypatch):
    import sources.base as base

    monkeypatch.setattr(base, "http_get_json", lambda *a, **k: None)  # simulate failure
    for conn in sources._REGISTRY:
        # safe_fetch must swallow everything into a list
        assert conn.safe_fetch(["q"], "Boston, MA", 4) == []


def test_keyed_connectors_unavailable_without_env(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.delenv("EPA_AQS_EMAIL", raising=False)
    monkeypatch.delenv("EPA_AQS_KEY", raising=False)
    from sources.census import CensusACSConnector
    from sources.epa_aqs import EPAAQSConnector

    assert CensusACSConnector().available() is False
    assert EPAAQSConnector().available() is False


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
def test_registry_filters_by_source_type(monkeypatch):
    import sources.base as base

    monkeypatch.setattr(base, "http_get_json", lambda *a, **k: OPENALEX_PAYLOAD)
    # Only academic connectors should run; open_data ones are filtered out.
    items = sources.fetch_evidence(["x"], "Boston, MA", source_types=["academic"], max_items=8)
    assert all(i.source_type == "academic" for i in items)


# --------------------------------------------------------------------------- #
# Evidence cache (Chroma) roundtrip
# --------------------------------------------------------------------------- #
def test_evidence_cache_roundtrip(tmp_path):
    cache = EvidenceCache(embed_fn=_fake_embedder(), path=str(tmp_path / "chroma"))
    items = [
        EvidenceItem(
            source_id="OPENALEX-A",
            title="Congestion pricing reduces traffic",
            source_type="academic",
            text="congestion pricing reduces downtown traffic significantly",
            relevance_score=0.9,
            credibility_score=0.85,
        ),
        EvidenceItem(
            source_id="MBTA-B",
            title="Transit ridership snapshot",
            source_type="open_data",
            text="mbta subway ridership and service alerts snapshot",
            relevance_score=0.7,
            credibility_score=0.95,
        ),
    ]
    assert cache.add(items) == 2
    got = cache.query(["congestion pricing traffic"], k=5)
    assert got, "expected a cache hit"
    # Best match should be the congestion-pricing academic item; credibility restored.
    assert got[0].source_id == "OPENALEX-A"
    assert got[0].credibility_score == pytest.approx(0.85)
    assert got[0].source_type == "academic"


# --------------------------------------------------------------------------- #
# Hybrid retrieve_policy_evidence (cache-first, then live, dedup + rank)
# --------------------------------------------------------------------------- #
def test_hybrid_dedup_and_rank(monkeypatch):
    monkeypatch.setattr(config, "MOCK_RETRIEVAL", False)
    monkeypatch.setattr(config, "LIVE_FETCH", True)

    # Empty cache -> forces live fetch.
    class _EmptyCache:
        def query(self, *a, **k):
            return []

        def add(self, items):
            return len(items)

    monkeypatch.setattr(retrieval, "_get_cache", lambda: _EmptyCache())

    dup_low = EvidenceItem(source_id="S-1", title="dup", text="t", relevance_score=0.5, credibility_score=0.5)
    dup_high = EvidenceItem(source_id="S-1", title="dup", text="t", relevance_score=0.9, credibility_score=0.9)
    other = EvidenceItem(source_id="S-2", title="other", text="t", relevance_score=0.6, credibility_score=0.6)
    monkeypatch.setattr(sources, "fetch_evidence", lambda *a, **k: [dup_low, dup_high, other])

    out = retrieval.retrieve_policy_evidence(["q"], geography="Boston, MA", top_k=6)
    ids = [e.source_id for e in out]
    assert ids == ["S-1", "S-2"]  # deduped by source_id, ranked by rel*cred
    assert out[0].relevance_score == 0.9  # kept the higher-scoring duplicate
