"""Knowledge-base search tools backed by Redis (RediSearch).

kb_search_bm25: full-text BM25 search (OR-semantics keyword query).
kb_search_vector: HNSW vector search over gemini-embedding-001 embeddings
(available only when the index was built with embeddings).

Replies are parsed via execute_command so both the classic array reply and
the Redis 8 map-style reply work regardless of redis-py version."""

import os
import re
import struct
from pathlib import Path
from collections import defaultdict

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
KB_EMBEDDINGS_PATH = Path(os.environ.get("KB_EMBEDDINGS_PATH", "/app/kb/embeddings.json"))
KB_INDEX = "kb_idx"
DOC_PREFIX = "doc:"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
LIVE_EMBEDDINGS = os.environ.get("KB_LIVE_EMBEDDINGS", "false").lower() == "true"
MAX_CONTENT_CHARS = 1600
TRUNCATION_MARKER = "\n[...truncated for latency...]"
SNIPPET_WINDOW_CHARS = 700

_client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
_genai_client = None


def _get_genai_client():
    """Reused genai client (one connection pool, not a new one per search)."""
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client()
    return _genai_client


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with gemini-embedding-001 via google-genai."""
    from google.genai import types

    # Reduced-dim output is unnormalized; the index uses COSINE, so that's fine.
    result = _get_genai_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return [e.values for e in result.embeddings]


def _decode(value) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _parse_search_reply(reply) -> list[dict]:
    """Normalize an FT.SEARCH reply (array or map shape) to result dicts."""
    if isinstance(reply, dict):
        results = reply.get(b"results", reply.get("results")) or []
        out = []
        for row in results:
            attrs = row.get(b"extra_attributes", row.get("extra_attributes")) or {}
            doc = {"doc_id": _decode(row.get(b"id", row.get("id", "")))}
            doc.update({_decode(k): _decode(v) for k, v in attrs.items()})
            out.append(doc)
        return out
    out = []
    for i in range(1, len(reply) - 1, 2):
        doc = {"doc_id": _decode(reply[i])}
        fields = reply[i + 1]
        for j in range(0, len(fields) - 1, 2):
            doc[_decode(fields[j])] = _decode(fields[j + 1])
        out.append(doc)
    return out


def _strip_score(docs: list[dict]) -> list[dict]:
    for doc in docs:
        doc.pop("score", None)
    return docs


def _query_terms(*values: str) -> list[str]:
    terms: list[str] = []
    seen = set()
    for value in values:
        for term in re.findall(r"\w+", (value or "").lower()):
            if len(term) < 3 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
    return terms


def _focused_content(content: str, terms: list[str]) -> str:
    if len(content) <= MAX_CONTENT_CHARS:
        return content
    lower = content.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not positions:
        keep = MAX_CONTENT_CHARS - len(TRUNCATION_MARKER)
        return content[:keep].rstrip() + TRUNCATION_MARKER

    start = max(0, min(positions) - SNIPPET_WINDOW_CHARS)
    end = min(len(content), start + MAX_CONTENT_CHARS - len(TRUNCATION_MARKER))
    snippet = content[start:end].strip()
    prefix = TRUNCATION_MARKER if start > 0 else ""
    suffix = TRUNCATION_MARKER if end < len(content) else ""
    return prefix + snippet + suffix


def _clip_content(docs: list[dict], *queries: str) -> list[dict]:
    terms = _query_terms(*queries)
    for doc in docs:
        content = doc.get("content")
        if isinstance(content, str):
            doc["content"] = _focused_content(content, terms)
    return docs


def kb_search_bm25(query: str, top_k: int = 3) -> list[dict]:
    """Full-text (BM25) search over the Rho-Bank knowledge base.

    Args:
        query: Keywords or a short phrase to search for. Matching is ranked,
            so extra keywords help rather than hurt.
        top_k: Number of documents to return.

    Returns:
        Matching documents with doc_id, title, and clipped content.
    """
    terms = re.findall(r"\w+", query.lower())
    if not terms:
        return []
    # OR-join: RediSearch defaults to AND, which zeroes out long queries.
    or_query = "|".join(dict.fromkeys(terms))
    reply = _client.execute_command(
        "FT.SEARCH", KB_INDEX, or_query,
        "LIMIT", "0", str(top_k),
        "RETURN", "2", "title", "content",
    )
    return _clip_content(_parse_search_reply(reply), query)


def kb_search_vector(query: str, top_k: int = 3) -> list[dict]:
    """Semantic (vector) search over the Rho-Bank knowledge base.

    Better than kb_search_bm25 when the query is a natural-language question
    rather than exact keywords.

    Args:
        query: A natural-language question or description.
        top_k: Number of documents to return.

    Returns:
        Matching documents with doc_id, title, and clipped content; or an error
        entry telling you to fall back to kb_search_bm25.
    """
    if not LIVE_EMBEDDINGS and not KB_EMBEDDINGS_PATH.exists():
        docs = kb_search_bm25(query, top_k)
        if docs:
            return docs
        return [
            {
                "error": "Vector search unavailable because the index has no "
                "embeddings. Use kb_search_bm25 with keywords instead."
            }
        ]

    try:
        vector = struct.pack(f"{EMBEDDING_DIM}f", *_embed([query])[0])
        reply = _client.execute_command(
            "FT.SEARCH", KB_INDEX, f"*=>[KNN {top_k} @embedding $vec AS score]",
            "PARAMS", "2", "vec", vector,
            "SORTBY", "score",
            "LIMIT", "0", str(top_k),
            "RETURN", "3", "title", "content", "score",
            "DIALECT", "2",
        )
        return _clip_content(_strip_score(_parse_search_reply(reply)), query)
    except Exception as e:
        return [
            {
                "error": f"Vector search unavailable ({type(e).__name__}). "
                "Use kb_search_bm25 with keywords instead."
            }
        ]


def kb_search_hybrid(query: str, keywords: str = "", top_k: int = 4) -> list[dict]:
    """BM25-first hybrid KB search with query-focused snippets.

    Args:
        query: Natural-language policy or procedure question.
        keywords: Optional exact product, action, tool, fee, or limit terms.
        top_k: Maximum merged documents to return.

    Returns:
        Deduplicated documents with doc_id, title, clipped content, and
        retrieval_source. Falls back to BM25 only when vectors are unavailable.
    """
    bm25_query = keywords.strip() or query
    merged: dict[str, dict] = {}
    ranks: dict[str, dict[str, int]] = defaultdict(dict)

    for rank, doc in enumerate(kb_search_bm25(bm25_query, top_k=top_k)):
        doc_id = doc.get("doc_id", f"bm25_{rank}")
        merged[doc_id] = {**doc, "retrieval_source": "bm25"}
        ranks[doc_id]["bm25_rank"] = rank

    if LIVE_EMBEDDINGS or KB_EMBEDDINGS_PATH.exists():
        vector_docs = kb_search_vector(query, top_k=top_k)
        if not (vector_docs and "error" in vector_docs[0]):
            for rank, doc in enumerate(vector_docs):
                doc_id = doc.get("doc_id", f"vector_{rank}")
                if doc_id in merged:
                    merged[doc_id]["retrieval_source"] = "bm25+vector"
                else:
                    merged[doc_id] = {**doc, "retrieval_source": "vector"}
                ranks[doc_id]["vector_rank"] = rank

    docs = []
    for doc_id, doc in merged.items():
        doc.update(ranks.get(doc_id, {}))
        docs.append(doc)

    docs.sort(
        key=lambda d: (
            0 if d.get("retrieval_source") == "bm25+vector" else 1,
            d.get("bm25_rank", 999),
            d.get("vector_rank", 999),
        )
    )
    return _clip_content(docs[:top_k], query, keywords)
