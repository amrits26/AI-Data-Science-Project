
from __future__ import annotations
from sentence_transformers import CrossEncoder

# Load cross-encoder model once
try:
    cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
except Exception:
    cross_encoder = None
"""Knowledge base semantic query utilities."""

import os
from pathlib import Path
from typing import Any


_VS_CACHE: Any = None
_VS_CACHE_INDEX: str | None = None
_VS_CACHE_MODEL: str | None = None


def _index_dir() -> Path:
    root = Path(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base"))
    return root / "index"


def _normalize_relevance_score(raw_score: float) -> float:
    """Convert backend score variants into a confidence-like 0..1 score."""
    score = float(raw_score)
    if score < 0.0:
        score = (score + 1.0) / 2.0
    elif score > 1.0:
        score = 1.0 / (1.0 + score)
    # Widen confidence for semantically related user phrasing.
    score = max(min(score, 1.0), 0.0) ** 0.5
    return score


def _load_vectorstore(index_dir: Path, model_name: str):
    global _VS_CACHE, _VS_CACHE_INDEX, _VS_CACHE_MODEL

    index_key = str(index_dir.resolve())
    if _VS_CACHE is not None and _VS_CACHE_INDEX == index_key and _VS_CACHE_MODEL == model_name:
        return _VS_CACHE

    from langchain_community.vectorstores import FAISS
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except Exception:
        from langchain_community.embeddings import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(model_name=model_name)
    try:
        vs = FAISS.load_local(index_key, embeddings, allow_dangerous_deserialization=False)
    except Exception as exc:
        message = str(exc)
        allow_trusted_local = os.getenv("KB_ALLOW_DANGEROUS_DESERIALIZATION", "1").strip().lower() not in {"0", "false", "no"}
        if "allow_dangerous_deserialization" in message and allow_trusted_local:
            vs = FAISS.load_local(index_key, embeddings, allow_dangerous_deserialization=True)
        else:
            raise

    _VS_CACHE = vs
    _VS_CACHE_INDEX = index_key
    _VS_CACHE_MODEL = model_name
    return vs


def query_knowledge_base(question: str, top_k: int = 4) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"status": "error", "message": "question is required"}

    idx = _index_dir()
    if not idx.exists():
        return {"status": "not_ready", "message": "vector index not found; run ingestion first"}

    try:
        from langchain_community.vectorstores import FAISS  # noqa: F401
        try:
            from langchain_huggingface import HuggingFaceEmbeddings  # noqa: F401
        except Exception:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: F401
    except Exception as exc:
        return {"status": "not_ready", "message": f"Missing required packages for RAG query: {exc}"}

    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    try:
        vs = _load_vectorstore(idx, model_name)
    except Exception as exc:
        return {"status": "error", "message": f"Failed to load vector index: {exc}"}

    k = max(int(top_k), 1)
    faiss_k = max(20, k)
    contexts: list[dict[str, Any]] = []

    # Retrieve top-20 from FAISS, then rerank with cross-encoder
    try:
        scored = vs.similarity_search_with_relevance_scores(q, k=faiss_k)
        for d, score in scored:
            contexts.append(
                {
                    "source": d.metadata.get("source"),
                    "chunk_index": d.metadata.get("chunk_index"),
                    "text": d.page_content,
                    "score": _normalize_relevance_score(float(score)),
                }
            )
    except Exception:
        try:
            scored = vs.similarity_search_with_score(q, k=faiss_k)
            for d, distance in scored:
                score = _normalize_relevance_score(1.0 / (1.0 + max(float(distance), 0.0)))
                contexts.append(
                    {
                        "source": d.metadata.get("source"),
                        "chunk_index": d.metadata.get("chunk_index"),
                        "text": d.page_content,
                        "score": score,
                    }
                )
        except Exception:
            docs = vs.similarity_search(q, k=faiss_k)
            for d in docs:
                contexts.append(
                    {
                        "source": d.metadata.get("source"),
                        "chunk_index": d.metadata.get("chunk_index"),
                        "text": d.page_content,
                        "score": 0.0,
                    }
                )

    # Cross-encoder reranking
    reranked = []
    try:
        if cross_encoder and contexts:
            pairs = [(q, c["text"]) for c in contexts]
            scores = cross_encoder.predict(pairs)
            for c, s in zip(contexts, scores):
                c["cross_score"] = float(s)
            reranked = sorted(contexts, key=lambda x: x["cross_score"], reverse=True)
            # Use cross-encoder score as new top_score
            top_score = float(reranked[0]["cross_score"]) if reranked else 0.0
            answer = "\n\n".join([f"[{c['source']}#{c['chunk_index']}] {c['text'][:320]}" for c in reranked[:k]])
            return {"status": "ok", "answer": answer, "contexts": reranked[:k], "top_score": top_score}
    except Exception:
        pass  # fallback to original

    # Fallback: use original FAISS order
    if not contexts:
        return {"status": "ok", "answer": "No relevant context found.", "contexts": []}
    answer = "\n\n".join([f"[{c['source']}#{c['chunk_index']}] {c['text'][:320]}" for c in contexts[:k]])
    top_score = float(contexts[0].get("score", 0.0)) if contexts else 0.0
    return {"status": "ok", "answer": answer, "contexts": contexts[:k], "top_score": top_score}
