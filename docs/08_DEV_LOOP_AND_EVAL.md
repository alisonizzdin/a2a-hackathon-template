# Dev Loop and Evaluation

## Baseline commands

From the template repo:

```bash
docker compose up --build
```

From the harness repo:

```bash
uv run a2a-hack smoke \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002
```

Run train:

```bash
uv run a2a-hack run \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002 \
  --tasks train \
  --save-to results/dev \
  --auto-resume

uv run tau2 view results/dev
```

Run test sparingly:

```bash
uv run a2a-hack run \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002 \
  --tasks test \
  --save-to results/test-check \
  --auto-resume
```

Do not tune directly to test.

## Failure taxonomy

When a task fails, assign exactly one primary cause and optional secondary causes.

```text
P1 personal intent error
- Personal misunderstood the user request.

P2 personal did not ask CS
- Personal guessed policy or tool ownership.

P3 personal missing-info failure
- Personal used a tool without required fields or asked for the wrong fields.

P4 personal tool execution failure
- Wrong user-side tool or wrong arguments.

P5 personal final-answer failure
- Action succeeded but final answer was incomplete or misleading.

C1 CS retrieval failure
- CS searched wrong terms or missed the relevant policy.

C2 CS reasoning failure
- CS retrieved relevant policy but made wrong decision.

C3 CS action-owner failure
- CS failed to say user-side vs bank-side clearly.

C4 CS bank-tool failure
- CS used wrong bank-side tool or wrong arguments.

C5 CS vague answer
- CS gave policy essay but no operational next step.

X1 contextId / isolation failure
- Tool call/session mismatch or cross-session leakage.

X2 timeout/rate-limit failure
- Too many calls, slow external dependency, or model/API rate limit.
```

## Transcript review template

For each failed task, create notes like:

```text
Task id:
Reward:
Primary failure code:
Secondary failure codes:

User request:

What personal-agent did:

What cs-agent did:

Tool calls:

Expected behavior:

Fix type:
- prompt
- RAG
- tool call logic
- context memory
- unknown

Patch:

Retest result:
```

## Metrics to track

Create a simple spreadsheet or markdown table:

```text
run_name | date | git_sha | train_score | failures | main_change | notes
```

Example:

```text
baseline | 2026-06-13 | abc123 | 0.42 | 19 | organiser template | weak CS answers
prompt-v1 | 2026-06-13 | def456 | 0.58 | 13 | prompt hardening | fewer tool arg errors
hybrid-rag-v1 | 2026-06-13 | ghi789 | 0.65 | 9 | kb_search_hybrid | fewer retrieval misses
```

## What to optimize first

Order of expected ROI:

```text
1. Personal prompt: do not guess, ask CS, execute user tools safely.
2. CS prompt: retrieve policy and return operational decisions.
3. Hybrid RAG: reduce CS retrieval misses.
4. Tool error recovery: retry safe malformed calls once.
5. Context ledger: avoid repeated questions in long tasks.
```

## Do not optimize this early

```text
- custom A2A executor
- external web search
- UI
- multiple LLM providers
- custom agent framework
- long-term customer memory
```

## Commit rhythm

Use small commits:

```bash
git add personal_agent/agent.py
git commit -m "Harden personal-agent policy coordination prompt"

git add cs_agent/agent.py
git commit -m "Make cs-agent return operational policy decisions"

git add cs_agent/rag_tools.py cs_agent/agent.py
git commit -m "Add hybrid Redis KB search tool"
```

Every commit should have a result directory:

```text
results/baseline
results/prompt-v1
results/cs-prompt-v1
results/hybrid-rag-v1
```
