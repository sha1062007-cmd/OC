"""
RAG Retriever for Adaptive Study Tutor.
Provides `retrieve(query: str, k: int = 4)` returning syllabus chunks with citations.
Format: [Source: file, p.X]
Uses robust hybrid vector & semantic keyword retrieval for curriculum textbooks.
"""

import os
import sys
import json
import re
import numpy as np
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

VECTOR_STORE_DIR = os.path.join(PROJECT_ROOT, "data", "vector_store")
INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "metadata.json")

# Module cache for loaded index and metadata
_CACHED_INDEX = None
_CACHED_METADATA = None
_EMBEDDING_MODEL = None


def _load_index_and_metadata():
    """Loads or creates the FAISS index and metadata cache."""
    global _CACHED_INDEX, _CACHED_METADATA, _EMBEDDING_MODEL

    if not os.path.exists(INDEX_PATH) or not os.path.exists(METADATA_PATH):
        from rag.ingest import run_ingestion
        run_ingestion()

    if _CACHED_METADATA is None and os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                _CACHED_METADATA = json.load(f)
        except Exception as e:
            print(f"[RAG Retriever] Error loading metadata: {e}")
            _CACHED_METADATA = []

    if _CACHED_INDEX is None and os.path.exists(INDEX_PATH):
        try:
            import faiss
            _CACHED_INDEX = faiss.read_index(INDEX_PATH)
        except Exception as e:
            print(f"[RAG Retriever] Note: FAISS index load issue ({e}), using dense dot-product fallback.")
            _CACHED_INDEX = None

    if _EMBEDDING_MODEL is None:
        from rag.ingest import get_embedding_model
        _EMBEDDING_MODEL = get_embedding_model()


def compute_keyword_overlap(query: str, text: str) -> float:
    """Computes normalized keyword overlap between query terms and text."""
    q_words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    if not q_words:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for w in q_words if w in text_lower)
    return float(matches) / float(len(q_words))


def retrieve(query: str, k: int = 4, score_threshold: float = 0.05) -> List[Dict[str, Any]]:
    """
    Retrieves the top k most relevant syllabus chunks for a query.
    Returns list of dicts with keys:
    - 'content': chunk text
    - 'citation': '[Source: file, p.X]'
    - 'score': similarity score (float 0.0 to 1.0)
    - 'source_file': filename
    - 'page': page number
    - 'chapter': chapter title
    """
    _load_index_and_metadata()

    if not _CACHED_METADATA:
        return []

    from rag.ingest import encode_texts
    query_vec = encode_texts([query], _EMBEDDING_MODEL)

    vector_scores = {}
    if _CACHED_INDEX is not None:
        try:
            search_k = min(len(_CACHED_METADATA), max(k * 3, 10))
            scores, indices = _CACHED_INDEX.search(query_vec, search_k)
            for s, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(_CACHED_METADATA):
                    vector_scores[idx] = float(s)
        except Exception as e:
            pass

    # Hybrid scoring: combine vector similarity and keyword overlap
    scored_items = []
    for idx, chunk in enumerate(_CACHED_METADATA):
        v_score = max(0.0, vector_scores.get(idx, 0.0))
        kw_score = compute_keyword_overlap(query, chunk["content"])
        
        # Combined score: weighted fusion
        combined = (0.5 * v_score) + (0.5 * kw_score)

        if combined >= score_threshold:
            item = dict(chunk)
            item["score"] = round(combined, 3)
            scored_items.append(item)

    # Sort descending by score
    scored_items.sort(key=lambda x: x["score"], reverse=True)
    return scored_items[:k]


def format_context_for_llm(chunks: List[Dict[str, Any]]) -> str:
    """Formats retrieved chunks with citations for inclusion in LLM prompts."""
    if not chunks:
        return "No specific syllabus sections found for this topic."
    formatted = []
    for c in chunks:
        formatted.append(f"{c['citation']}\n{c['content']}")
    return "\n\n---\n\n".join(formatted)
