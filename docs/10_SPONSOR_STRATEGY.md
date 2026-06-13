# Sponsor Strategy

Use sponsor tools only where they help the scored benchmark.

## A2A Protocol

A2A is core. The agents must interoperate over A2A.

What to show:

```text
- personal-agent and cs-agent as separate A2A services
- contextId propagation
- final Task/Message response behavior
- clean communication between agents
- compatibility with held-out agents
```

Do not overbuild a custom A2A executor unless needed. The default ADK executor is good enough if smoke passes.

## Redis

Redis is highly relevant.

Scored path:

```text
- Redis KB index for CS RAG
- optional per-context memory / ledger
```

Good sponsor narrative:

```text
Redis is the shared context layer. The CS agent retrieves policy from Redis RAG and can store per-session decisions, missing fields, and tool outcomes under context-scoped keys.
```

Implementation priority:

```text
1. Keep existing Redis RAG working.
2. Add hybrid search.
3. Add per-context ledger only if time allows.
```

## Linkup

Do **not** use Linkup in the scored runtime path for Track 1 unless organisers explicitly confirm external web search is expected.

Reason:

```text
- tasks are controlled by the harness
- policies live in local KB
- external web data can be irrelevant or contradictory
- web calls add latency and timeout risk
- held-out scoring rewards benchmark reliability, not broad research
```

Possible use:

```text
- side demo only
- pre-event research by humans
- docs/source discovery outside marked runs
```

## Sierra

Use Sierra as conceptual inspiration for customer-service behavior.

Useful ideas:

```text
- natural user-safe final answers
- clear escalation paths
- operationally useful customer interactions
```

Do not integrate Sierra runtime unless there is a hackathon-specific API path and it clearly helps the harness.

## Cognition / Devin

Use Devin or similar coding agents as a build assistant only.

Good tasks:

```text
- implement kb_search_hybrid
- write unit tests for retrieval merge/dedup
- inspect train transcripts
- propose prompt patches
- check docker compose build
```

Do not make Devin part of the runtime architecture.

## Summary

```text
Use heavily: A2A, Redis
Use optionally: Cognition/Devin for coding
Use as inspiration: Sierra
Avoid in scored runtime: Linkup
```
