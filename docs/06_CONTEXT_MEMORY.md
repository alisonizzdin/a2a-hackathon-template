# Redis Context Memory and Ledger

Redis is useful, but only as **per-context memory**. Do not build global long-term customer memory across benchmark sessions.

## Why use Redis

Use Redis to make the agents look coordinated and robust within a session:

```text
- remember known facts
- remember what CS already decided
- remember missing fields
- record tool calls and outcomes
- avoid asking the same question twice
- produce clearer final answers
```

## Hard rule

Every key must include `contextId`.

Good:

```text
ctx:ctx42:facts
ctx:ctx42:missing_fields
ctx:ctx42:cs_decisions
```

Bad:

```text
customer:facts
latest_decision
user_profile
```

The benchmark runs simulations concurrently. Global keys can leak data and destroy score.

## Suggested keys

```text
ctx:{contextId}:facts             Redis hash
ctx:{contextId}:missing_fields    Redis set or JSON string
ctx:{contextId}:cs_decisions      Redis list
ctx:{contextId}:tool_calls        Redis stream
ctx:{contextId}:final_state       Redis hash
ctx:{contextId}:summary           Redis string
```

## Minimal ledger event format

Use JSON values like:

```json
{
  "time": "2026-06-13T12:00:00Z",
  "agent": "personal-agent",
  "event_type": "cs_request",
  "content": {
    "intent": "submit referral",
    "known_facts": ["friend name: Dana"],
    "missing_facts": ["friend contact"]
  }
}
```

## Useful internal functions

Add these only after prompt/RAG improvements.

```python
async def remember_fact(key: str, value: str, tool_context: ToolContext) -> dict:
    """Store a context-scoped fact."""

async def recall_facts(tool_context: ToolContext) -> dict:
    """Return known facts for the current context only."""

async def log_resolution_step(event_type: str, content_json: str, tool_context: ToolContext) -> dict:
    """Append a context-scoped ledger event."""
```

## Where to add memory tools

The template services already connect to Redis in the CS container for RAG. Personal-agent may not have Redis URL configured by default.

Recommended order:

1. Add ledger to `cs-agent` first, because it already depends on Redis.
2. Only add Redis to `personal-agent` if we need it.
3. Keep memory tools behind simple function calls; do not make memory a critical path for every turn.

## What memory should not do

Do not store:

```text
- facts from one context for use in another context
- customer identity outside the task context
- generated assumptions
- failed guesses as facts
- hidden test-specific behavior
```

## Sponsor narrative

For demos or stage presentation, we can say:

> Redis acts as the context ledger for the two-agent banking workflow. Each session has isolated memory of known customer facts, policy decisions, missing fields, and tool outcomes, so the agents coordinate without leaking data across concurrent simulations.

But for scoring, reliability matters more than narrative. Keep Redis additions small and safe.
