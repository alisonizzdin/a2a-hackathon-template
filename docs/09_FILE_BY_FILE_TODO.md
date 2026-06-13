# File-by-File TODO

Use this as the coding checklist after cloning the organiser template.

## 1. `personal_agent/agent.py`

### First change

Replace `INSTRUCTION` with the personal-agent prompt in `04_PROMPTS.md`.

Keep:

```python
MODEL = os.environ.get("MODEL", "gemini-3.5-flash")

tools=[EnvApiToolset(), ask_customer_service]
```

### What this should improve

```text
- personal asks CS for policy instead of guessing
- personal asks user for missing fields
- personal uses user-side tools safely
- personal handles CS replies robustly
```

### Do not change yet

```text
- do not remove EnvApiToolset
- do not remove ask_customer_service
- do not replace Gemini model
- do not add external APIs
```

## 2. `cs_agent/agent.py`

### First change

Replace `RAG_GUIDANCE` with the CS prompt in `04_PROMPTS.md`.

Keep:

```python
instruction=POLICY_PATH.read_text() + RAG_GUIDANCE
```

### Later change after hybrid search

```python
from rag_tools import kb_search_bm25, kb_search_vector, kb_search_hybrid

tools=[EnvApiToolset(), kb_search_bm25, kb_search_vector, kb_search_hybrid]
```

### What this should improve

```text
- CS searches KB before answering
- CS returns allowed / denied / need-more-info
- CS states action owner
- CS lists required fields
- CS gives next step to personal
```

## 3. `cs_agent/rag_tools.py`

### First change

Add:

```python
kb_search_hybrid(query: str, keywords: str = "", top_k: int = 8)
```

Use the implementation sketch in `05_RAG_STRATEGY.md`.

### What this should improve

```text
- fewer retrieval misses
- BM25 and vector results combined
- vector failure does not break answers
- CS has one preferred search tool
```

## 4. `cs_agent/ingest.py`

Do not change in the first coding session.

Possible later improvements:

```text
- chunk long docs
- add metadata fields
- boost policy chunks
- pre-bake index for faster startup
```

Change only if train transcripts show retrieval misses after hybrid search.

## 5. `personal_agent/env_toolset.py` and `cs_agent/env_toolset.py`

Do not change unless smoke reveals a real problem.

These files already:

```text
- fetch dynamic tools from env API
- use contextId through ADK session id
- provide call_env_tool fallback
```

They are critical to conformance.

## 6. `personal_agent/cs_client_tool.py`

Do not change initially.

This file already:

```text
- contacts CS_AGENT_URL over A2A
- propagates contextId
- reads final text from Message or Task artifacts/status
- uses a 300s timeout
```

Changing it risks contextId or A2A conformance issues.

## 7. `docker-compose.yml`

Do not change service names or exposed ports.

Required services:

```text
personal-agent
cs-agent
redis
```

Do not add runtime services unless absolutely necessary.

## 8. `kb/`

The KB is public and preprocessing is allowed.

First pass:

```text
- leave KB documents unchanged
- improve retrieval tools and prompts
```

Later:

```text
- add derived files only if useful
- document any preprocessing clearly
- avoid hidden test-specific hacks
```

## 9. `docs/`

Copy this doc pack into:

```text
bank-resolution-agent/docs/
```

Commit docs with the first implementation branch:

```bash
git add docs
git commit -m "Add implementation docs for A2A bank resolution agent"
```
