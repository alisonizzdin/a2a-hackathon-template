# CS RAG Strategy

The CS agent's RAG pipeline is likely the highest-leverage technical improvement after prompts.

## Current template behavior

The template already has:

```text
cs_agent/ingest.py
- builds a Redis full-text + vector index at startup
- indexes kb/documents
- uses embedding cache if present
- falls back to BM25-only if embeddings are unavailable

cs_agent/rag_tools.py
- kb_search_bm25(query, top_k=5)
- kb_search_vector(query, top_k=5)
```

## Problems to fix

A plain LLM choosing between BM25 and vector search can fail in these ways:

```text
- searches a vague query and misses exact policy terms
- gets vector-only results without exact tool/procedure names
- gets BM25 results that match keywords but not the customer intent
- retrieves too many long documents and loses the key rule
- does not retry with product/action keywords
```

## Add kb_search_hybrid

Add a deterministic hybrid helper so the model has a better default search tool.

Suggested behavior:

```text
kb_search_hybrid(query: str, keywords: str = "", top_k: int = 8) -> list[dict]

1. Build a compact BM25 query from `keywords` if provided, else from `query`.
2. Call kb_search_bm25(..., top_k=top_k).
3. Call kb_search_vector(..., top_k=top_k) if available.
4. Merge by doc_id.
5. Preserve source flags: bm25, vector, or both.
6. Put dual-source matches first.
7. Return title + content + retrieval metadata.
8. If vector fails, return BM25 results plus a note; never crash.
```

Minimal implementation shape:

```python
def kb_search_hybrid(query: str, keywords: str = "", top_k: int = 8) -> list[dict]:
    """Hybrid Redis KB search for policy/procedure lookup.

    Args:
        query: Natural language policy/procedure question.
        keywords: Optional exact terms such as product name, action name, tool name, fee, limit.
        top_k: Maximum merged documents to return.

    Returns:
        Deduplicated documents with doc_id, title, content, and retrieval_source.
    """
    bm25_query = keywords.strip() or query
    bm25_docs = kb_search_bm25(bm25_query, top_k=top_k)

    vector_docs = []
    vector_error = None
    try:
        vector_docs = kb_search_vector(query, top_k=top_k)
        if vector_docs and "error" in vector_docs[0]:
            vector_error = vector_docs[0]["error"]
            vector_docs = []
    except Exception as e:
        vector_error = f"vector search failed: {type(e).__name__}: {e}"

    merged = {}

    for rank, doc in enumerate(bm25_docs):
        doc_id = doc.get("doc_id", f"bm25_{rank}")
        merged[doc_id] = {**doc, "retrieval_source": "bm25", "bm25_rank": rank}

    for rank, doc in enumerate(vector_docs):
        doc_id = doc.get("doc_id", f"vector_{rank}")
        if doc_id in merged:
            merged[doc_id]["retrieval_source"] = "bm25+vector"
            merged[doc_id]["vector_rank"] = rank
        else:
            merged[doc_id] = {**doc, "retrieval_source": "vector", "vector_rank": rank}

    docs = list(merged.values())
    docs.sort(key=lambda d: (
        0 if d.get("retrieval_source") == "bm25+vector" else 1,
        d.get("bm25_rank", 999),
        d.get("vector_rank", 999),
    ))

    if vector_error and docs:
        docs.append({"note": vector_error})

    return docs[:top_k]
```

Then update `cs_agent/agent.py`:

```python
from rag_tools import kb_search_bm25, kb_search_vector, kb_search_hybrid

tools=[EnvApiToolset(), kb_search_bm25, kb_search_vector, kb_search_hybrid]
```

## Query rewrite patterns

The CS agent should search with both customer language and exact bank terms.

Examples:

```text
User: "Can I send a referral to my friend?"
Hybrid query: "referral friend account submit referral policy required fields"
Keywords: "referral submit_referral Blue Account"

User: "I want to reverse a suspicious charge"
Hybrid query: "transaction dispute suspicious charge required fields policy"
Keywords: "dispute transaction charge"

User: "Why was my application rejected?"
Hybrid query: "application rejection explanation eligibility policy customer service"
Keywords: "application rejected eligibility"
```

## Retrieval answer discipline

CS should not stop at retrieval. It should convert retrieval into a decision.

Bad:

```text
I found a policy about referrals.
```

Good:

```text
DECISION: NEED_MORE_INFO
ACTION_OWNER: personal-agent
REQUIRED_FIELDS:
- referred person's full name
- referred person's contact details
RECOMMENDED_TOOL:
- side: user-side
- name: submit_referral
POLICY_BASIS:
- Referrals are submitted from the customer side after verification.
NEXT_STEP_FOR_PERSONAL:
Ask the user for the friend's contact details, then use the user-side referral tool if available.
```

## Optional ingest improvements

Only do this after hybrid search is working.

Possible improvements:

```text
- Split very long documents into smaller chunks.
- Add derived title prefixes like product/action/category.
- Boost policy.md-derived chunks.
- Store metadata fields such as product, action, required_tools, and eligibility_terms.
```

Keep it simple unless train failures clearly point to retrieval misses.
