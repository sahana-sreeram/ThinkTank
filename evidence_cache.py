"""Local Chroma-backed cache of policy evidence (OWNER: Person 2).

This is the "local" half of the hybrid retrieval strategy: evidence fetched live
from external connectors (``sources/``) is embedded and upserted here, so repeat
runs — and fully offline runs — are served from the local vector store without
hitting the network again. Aligns with the project's local-first design.

The embedding function is injectable so the cache is testable without Ollama; the
default uses ``ingestion.get_embeddings`` (nomic-embed-text via Ollama).
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from config import DB_PATH, EVIDENCE_COLLECTION, HNSW_SPACE
from logger import logger
from models import EvidenceItem

EmbedFn = Callable[[Sequence[str]], List[List[float]]]

_META_KEYS = (
    "title",
    "organization",
    "source_type",
    "publication_date",
    "geography",
    "page",
    "credibility_score",
)


def _default_embedder() -> EmbedFn:
    from ingestion import get_embeddings

    model = get_embeddings()
    return lambda texts: [model.embed_query(t) for t in texts]


class EvidenceCache:
    """Thin wrapper over a Chroma collection storing ``EvidenceItem``s."""

    def __init__(self, embed_fn: Optional[EmbedFn] = None, path: str = DB_PATH):
        self._embed = embed_fn
        self._path = path
        self._collection = None

    # -- lazy resources -----------------------------------------------------
    @property
    def embed(self) -> EmbedFn:
        if self._embed is None:
            self._embed = _default_embedder()
        return self._embed

    @property
    def collection(self):
        if self._collection is None:
            from db_connection import ChromaDBConnection

            db = ChromaDBConnection(self._path)
            self._collection = db.get_collection(
                EVIDENCE_COLLECTION, {"hnsw:space": HNSW_SPACE}
            )
        return self._collection

    # -- writes -------------------------------------------------------------
    def add(self, items: Sequence[EvidenceItem]) -> int:
        """Embed and upsert items. De-duplicates by ``source_id`` via upsert."""
        items = [it for it in items if it and it.text.strip()]
        if not items:
            return 0
        # Collapse duplicate source_ids within this batch (upsert needs unique ids).
        unique: dict[str, EvidenceItem] = {}
        for it in items:
            unique.setdefault(it.source_id, it)
        batch = list(unique.values())
        embeddings = self.embed([it.text for it in batch])
        metadatas = []
        for it in batch:
            meta = {}
            for k in _META_KEYS:
                v = getattr(it, k, None)
                if v is not None:
                    meta[k] = v
            metadatas.append(meta)
        self.collection.upsert(
            ids=[it.source_id for it in batch],
            documents=[it.text for it in batch],
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info("evidence_cache: upserted %d items", len(batch))
        return len(batch)

    # -- reads --------------------------------------------------------------
    def query(
        self,
        queries: List[str],
        geography: Optional[str] = None,
        source_types: Optional[List[str]] = None,
        k: int = 12,
    ) -> List[EvidenceItem]:
        """Similarity search; returns best-scoring unique evidence items.

        ``relevance_score`` on returned items is the cosine similarity to the
        nearest query; ``credibility_score`` is restored from stored metadata.
        """
        if not queries or self.collection.count() == 0:
            return []
        where = {"source_type": {"$in": source_types}} if source_types else None
        vectors = self.embed(queries)
        best: dict[str, tuple[float, str, dict]] = {}
        for vec in vectors:
            res = self.collection.query(
                query_embeddings=[vec],
                n_results=min(k, max(1, self.collection.count())),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            ids = res.get("ids", [[]])[0]
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            for sid, doc, meta, dist in zip(ids, docs, metas, dists):
                sim = 1.0 - float(dist)  # cosine distance -> similarity
                if sid not in best or sim > best[sid][0]:
                    best[sid] = (sim, doc, meta or {})

        items: list[EvidenceItem] = []
        for sid, (sim, doc, meta) in best.items():
            items.append(
                EvidenceItem(
                    source_id=sid,
                    title=meta.get("title", sid),
                    organization=meta.get("organization"),
                    source_type=meta.get("source_type", "other"),
                    publication_date=meta.get("publication_date"),
                    geography=meta.get("geography"),
                    page=meta.get("page"),
                    text=doc,
                    relevance_score=round(max(0.0, min(1.0, sim)), 3),
                    credibility_score=float(meta.get("credibility_score", 0.0)),
                )
            )
        items.sort(key=lambda e: e.relevance_score * e.credibility_score, reverse=True)
        return items[:k]
