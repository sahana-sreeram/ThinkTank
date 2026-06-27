from collections import defaultdict

from logger import logger
from typing import List, Optional

from config import DB_PATH, HNSW_SPACE


def _lazy_retrieval_deps():
    """Import Chroma/embeddings only when a real retrieval is requested.

    Keeps the module importable (and mock mode runnable) without chromadb/ollama.
    """
    from db_connection import ChromaDBConnection
    from ingestion import get_embeddings

    return ChromaDBConnection, get_embeddings

def retrieve_documents(queries: List[str], collection_name: str) -> List[str]:
    """
    Performs vector search on collections with dense retrieval.

    Args:
        queries (List[str]): List of translated user queries.
        collection_name (str): Name of the collection in ChromaDB.

    Returns:
        dict: {
            'query_list': List[str],           # The input queries
            'context': List[str],              # List of document texts
            'retrieved_docs': List[dict]       # List of dicts with 'text' and 'source'
        }
    """
    logger.info("Performing retrieval...")
    ChromaDBConnection, get_embeddings = _lazy_retrieval_deps()
    db = ChromaDBConnection(DB_PATH)
    collection = db.get_collection(name=collection_name, metadata={"hnsw:space": HNSW_SPACE})
    embeddings = get_embeddings()

    logger.info("Fetching all documents from ChromaDB for sparse retrieval...")

    dense_scores = defaultdict(float)
    for query in queries:
        query_vector = embeddings.embed_query(query)
        retrieved = collection.query(query_embeddings=[query_vector], n_results=10, include=["distances"])
        for i, doc_id in enumerate(retrieved["ids"][0]):
            # Convert distance to similarity score: similarity = 1 - distance
            raw_dist = 1 - retrieved["distances"][0][i]
            score = 1 - raw_dist if HNSW_SPACE == "cosine" else -raw_dist
            dense_scores[doc_id] += score

    # top-k by combined dense score
    top_ids = [doc for doc, _ in sorted(dense_scores.items(),
                                        key=lambda x: x[1],
                                        reverse=True)][:10]

    docs = collection.get(ids=top_ids, include=["documents", "metadatas"])
    dense_results = [ {'text': doc_text, 'source': metadata['source']}  for _, doc_text, metadata in zip(top_ids, docs["documents"], docs["metadatas"])]
    logger.info(f"Retrieved {len(dense_results)} documents from collection '{collection_name}'.")

    #Display unique sources in Streamlit app
    unique_sources = set(result['source'] for result in dense_results)
    # st.markdown(f"### References from collection: {collection_name}:")
    # st.session_state.markdown_log.append("### References:")
    # for source in unique_sources:
    #     st.markdown(f"- {source}")
    #     st.session_state.markdown_log.append(f"- {source}")

    # websocket.send_json({'name': 'Retrieved Documents', 'content': f"Retrieved {len(dense_results)} documents from collection '{collection_name}'."})
    # for source in unique_sources:
    #     websocket.send_json({'name': f'- {source}', 'content': ''})


    # Keep full document objects for tool call output
    tool_output = {
        'query_list': queries,
        'context': [result['text'] for result in dense_results],
        'retrieved_docs': dense_results  # Include full document objects with text and source
    }
    return tool_output

# ---------------------------------------------------------------------------
# Policy evidence retrieval (NEW public seam — OWNER: Person 2)
# ---------------------------------------------------------------------------

def _mock_evidence(queries: List[str], geography: Optional[str]):
    """Domain-neutral placeholder evidence for mock/dev mode.

    Generates clearly-labeled PLACEHOLDER EvidenceItems templated to the query and
    geography so the rest of the team is unblocked for ANY policy domain before the
    real Chroma collection exists. These are not real sources."""
    from models import EvidenceItem

    topic = (queries[0] if queries else "the policy question").strip()
    geo = geography or "the target geography"
    return [
        EvidenceItem(
            source_id="PLACEHOLDER-GOV",
            title=f"Government Review Relevant to: {topic}",
            organization="(placeholder) Government Source",
            source_type="government_report",
            publication_date="2023",
            geography=geo,
            page=1,
            text=f"Placeholder government evidence relevant to {topic} in {geo}.",
            relevance_score=0.9,
            credibility_score=0.85,
        ),
        EvidenceItem(
            source_id="PLACEHOLDER-ACADEMIC",
            title=f"Comparative Study Relevant to: {topic}",
            organization="(placeholder) Academic Source",
            source_type="academic",
            publication_date="2022",
            geography="Comparable jurisdictions",
            page=4,
            text=f"Placeholder academic evidence on outcomes of similar policies to {topic}.",
            relevance_score=0.86,
            credibility_score=0.82,
        ),
        EvidenceItem(
            source_id="PLACEHOLDER-CASE",
            title=f"Case Study Relevant to: {topic}",
            organization="(placeholder) Case Study Source",
            source_type="case_study",
            publication_date="2021",
            geography="Comparable jurisdiction",
            page=2,
            text=f"Placeholder case-study evidence on implementing a policy like {topic}.",
            relevance_score=0.8,
            credibility_score=0.75,
        ),
    ]


# Reused across calls so the embedder + Chroma collection are initialized once.
_CACHE = None


def _get_cache():
    global _CACHE
    if _CACHE is None:
        from evidence_cache import EvidenceCache

        _CACHE = EvidenceCache()
    return _CACHE


def _rank_and_dedup(items, top_k: int):
    """Deduplicate by source_id (keep best) and rank by relevance * credibility."""
    best = {}
    for e in items:
        score = e.relevance_score * e.credibility_score
        cur = best.get(e.source_id)
        if cur is None or score > cur.relevance_score * cur.credibility_score:
            best[e.source_id] = e
    ranked = sorted(
        best.values(),
        key=lambda e: e.relevance_score * e.credibility_score,
        reverse=True,
    )
    return ranked[:top_k]


def _hybrid_evidence(queries, geography, source_types, top_k):
    """Cache-first, then live-fetch-and-cache (the hybrid retrieval strategy)."""
    from config import LIVE_FETCH, EVIDENCE_FETCH_BUDGET

    items = []
    cache = _get_cache()
    try:
        items = cache.query(queries, geography, source_types, k=top_k * 3)
    except Exception as exc:  # noqa: BLE001 - cache must never break a run
        logger.warning("evidence cache query failed: %s", exc)

    if LIVE_FETCH and len(items) < top_k:
        import sources

        fresh = sources.fetch_evidence(
            queries, geography, source_types, max_items=EVIDENCE_FETCH_BUDGET
        )
        if fresh:
            try:
                cache.add(fresh)
            except Exception as exc:  # noqa: BLE001
                logger.warning("evidence cache write failed: %s", exc)
            items = items + fresh
    return items


def retrieve_policy_evidence(
    queries: List[str],
    geography: Optional[str] = None,
    source_types: Optional[List[str]] = None,
    top_k: int = 6,
):
    """Retrieve ranked, deduplicated, citable policy evidence.

    - MOCK_RETRIEVAL (the default when MOCK_MODE): returns fixture EvidenceItems so
      the rest of the team is unblocked.
    - Real path: hybrid retrieval — query the local Chroma evidence cache first,
      then live-fetch from external connectors (``sources/``) when the cache is
      thin, caching new evidence for next time. Results are deduplicated by
      source_id and ranked by relevance * credibility.

    Note: gated on MOCK_RETRIEVAL (not MOCK_MODE) so real citations can flow into
    mock agents — set POLICY_MOCK_RETRIEVAL=0 to turn sources real independently.
    """
    from config import MOCK_RETRIEVAL

    if MOCK_RETRIEVAL:
        items = _mock_evidence(queries, geography)
        if source_types:
            items = [e for e in items if e.source_type in source_types]
    else:
        items = _hybrid_evidence(queries, geography, source_types, top_k)

    out = _rank_and_dedup(items, top_k)
    logger.info(
        "retrieve_policy_evidence returned %d items (mock=%s)", len(out), MOCK_RETRIEVAL
    )
    return out
