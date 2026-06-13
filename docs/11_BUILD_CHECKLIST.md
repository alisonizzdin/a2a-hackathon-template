# Build Checklist

## Repo setup

```text
[ ] Clone a2anet/a2a-hackathon-template.
[ ] Clone a2anet/a2a-hackathon next to it.
[ ] Copy these docs into template repo under docs/.
[ ] Create branch bank-resolution-v1.
[ ] Configure .env.
[ ] docker compose up --build succeeds.
[ ] smoke passes.
[ ] baseline train result saved.
```

## First implementation pass

```text
[ ] Replace personal-agent prompt.
[ ] Replace CS-agent prompt.
[ ] Run smoke.
[ ] Run train.
[ ] Classify failures.
[ ] Commit prompt changes.
```

## RAG pass

```text
[ ] Add kb_search_hybrid.
[ ] Add it to CS-agent tools.
[ ] Update CS prompt to prefer hybrid search.
[ ] Run smoke.
[ ] Run train.
[ ] Compare retrieval failures against baseline.
[ ] Commit RAG changes.
```

## Robustness pass

```text
[ ] Personal handles plain-English CS replies.
[ ] Personal asks targeted follow-up when CS is vague.
[ ] CS answers messy personal-agent requests.
[ ] CS states action owner in every policy answer.
[ ] CS lists required fields before action.
[ ] No tool calls use placeholder values.
[ ] No external web calls in scored path.
```

## Context / Redis pass

```text
[ ] All optional memory keys include contextId.
[ ] No cross-context global customer memory.
[ ] Tool-call ledger is per-context.
[ ] Memory failures do not break the main task path.
```

## Final submission pass

```text
[ ] Clean checkout builds.
[ ] docker compose up --build works.
[ ] smoke passes.
[ ] train run saved.
[ ] feedback submission made.
[ ] feedback transcripts reviewed.
[ ] No model rule violation.
[ ] No compose-shape violation.
[ ] No contextId violation.
[ ] Latest commit pushed to public GitHub repo.
[ ] Repo URL and Vertex API key submitted.
```

## One-sentence team strategy

> We are not building a flashy product; we are building the most reliable, interoperable two-agent banking resolution system in the benchmark.
