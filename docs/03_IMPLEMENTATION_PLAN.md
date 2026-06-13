# Implementation Plan

## Phase 0 — Baseline

Run the starter unchanged.

```bash
docker compose up --build
```

In the harness repo:

```bash
uv run a2a-hack smoke \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002

uv run a2a-hack run \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002 \
  --tasks train \
  --save-to results/baseline \
  --auto-resume

uv run tau2 view results/baseline
```

Commit before changing anything:

```bash
git checkout -b bank-resolution-v1
git add .
git commit -m "Baseline organiser template"
```

## Phase 1 — Prompt hardening

Change only:

```text
personal_agent/agent.py
cs_agent/agent.py
```

Goal:

```text
- Personal agent asks CS better questions.
- CS agent returns actionable policy decisions.
- Both agents ask for missing info instead of hallucinating.
```

Use the prompt blocks in `04_PROMPTS.md`.

Run smoke and train again:

```bash
uv run a2a-hack smoke --personal-url http://localhost:9001 --cs-url http://localhost:9002
uv run a2a-hack run --personal-url http://localhost:9001 --cs-url http://localhost:9002 --tasks train --save-to results/prompt-v1 --auto-resume
uv run tau2 view results/prompt-v1
```

Classify every failure using `08_DEV_LOOP_AND_EVAL.md`.

## Phase 2 — Add structured inter-agent messages

Still only prompt-level unless needed.

Personal-agent should ask CS using this shape:

```text
CUSTOMER_INTENT:
...

KNOWN_FACTS:
- ...

MISSING_FACTS:
- ...

REQUEST:
1. Is this allowed?
2. What action owner should handle it: personal-agent, cs-agent, user, or none?
3. What tools may be needed?
4. What fields are required?
5. What should I ask the user next?
```

CS-agent should answer using this shape:

```text
DECISION: ALLOWED | DENIED | NEED_MORE_INFO | COMPLETED | ESCALATE
ACTION_OWNER: personal-agent | cs-agent | user | none
REQUIRED_FIELDS:
- ...
RECOMMENDED_TOOL:
- side: user-side | bank-side | none
- name: ...
POLICY_BASIS:
- ...
NEXT_STEP_FOR_PERSONAL:
...
USER_SAFE_SUMMARY:
...
```

The personal agent must also handle plain English from a held-out CS agent. Treat the schema as preferred, not mandatory.

## Phase 3 — Improve CS RAG

Change:

```text
cs_agent/rag_tools.py
cs_agent/ingest.py   # only if needed
cs_agent/agent.py
```

Add a combined retrieval tool:

```text
kb_search_hybrid(query, keywords=None, top_k=8)
```

It should:

```text
1. Run BM25.
2. Run vector search if available.
3. Merge and deduplicate by doc_id.
4. Return compact documents with title, content, source search type, and rank.
5. If vector search fails, return BM25-only results without crashing.
```

Update CS prompt so it prefers `kb_search_hybrid` for policy questions, but can fall back to `kb_search_bm25` and `kb_search_vector`.

## Phase 4 — Add optional Redis context ledger

Only add this after Phase 1–3 improve scores.

Use Redis memory for per-context notes:

```text
ctx:{contextId}:facts
ctx:{contextId}:cs_decisions
ctx:{contextId}:tool_calls
ctx:{contextId}:missing_fields
ctx:{contextId}:final_state
```

Do not store global customer memory outside contextId.

Possible tools:

```text
remember_context_fact(key, value)
recall_context_summary()
log_resolution_step(step_type, content)
```

Keep these internal. They are useful for multi-turn tasks and sponsor narrative, but not required for the first pass.

## Phase 5 — Interoperability hardening

Optimize for held-out pairings.

Personal-agent compatibility:

```text
- Does not assume CS returns our schema.
- Asks precise questions.
- Can recover from vague CS answers by asking one follow-up.
- Uses own tools when CS says action is user-side.
```

CS-agent compatibility:

```text
- Answers unknown personal agents directly and clearly.
- States allowed / denied / need more info.
- Identifies user-side vs bank-side action.
- Does not require our personal-agent's message format.
```

## Phase 6 — Submission pass

Before submitting:

```text
[ ] docker compose up --build from clean checkout succeeds.
[ ] smoke passes.
[ ] train score is recorded.
[ ] feedback submission made.
[ ] transcripts checked for model compliance.
[ ] no non-Gemini chat model added.
[ ] contextId appears in every env call path.
[ ] no cross-session Redis keys without contextId.
[ ] no runtime dependency on external web search.
```
