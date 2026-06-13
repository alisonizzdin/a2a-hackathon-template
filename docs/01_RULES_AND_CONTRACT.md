# Rules and Contract

This file is the operating contract for the build. Do not violate it while optimizing.

## Fixed public services

The submitted repo must keep the organiser compose shape:

```text
personal-agent :9001
cs-agent       :9002
redis          :6379
```

The two public A2A agents are:

| Service | Role | Owns |
|---|---|---|
| `personal-agent` | User's personal banking assistant | user-side environment tools, user goal, clarification questions, final user response |
| `cs-agent` | Bank customer-service agent | bank-side environment tools, banking policy, KB search through Redis RAG |

There is no third public research agent in the starter repo. Any research-like behavior should be implemented inside `cs-agent` as internal logic/tools.

## Model rule

Marked runs must use:

```text
gemini-3.5-flash
```

Do not switch the chat model in committed code. Keep this default:

```python
MODEL = os.environ.get("MODEL", "gemini-3.5-flash")
```

The vector index can use `gemini-embedding-001`, which the template already does.

## A2A wire contract

If we keep the default ADK executor, most of this is already handled. Still, every change should respect:

```text
- Serve A2A over JSON-RPC.
- Expose an Agent Card at service root.
- Support message/send with text parts.
- Return final user-visible text in a Message or Task artifact/status message.
- Do not expect intermediate tool calls to be visible to the caller.
```

Do not rewrite the executor unless we have a specific reason and smoke still passes afterward.

## contextId discipline

Every incoming A2A message has a `contextId`. Treat it as the session key.

Rules:

```text
- Every env API tool call must use the same contextId.
- Every personal-agent → cs-agent A2A message must use the same contextId.
- Redis memory keys must include contextId.
- Do not leak facts across contextIds.
```

The template's `EnvApiToolset` already maps ADK session id to the harness session id. Avoid breaking that path.

## Environment tools

Each agent must fetch tools from the harness env API. Do not hardcode tools.

The env API exposes:

```text
GET  {ENV_API_URL}/sessions/{contextId}/tools
POST {ENV_API_URL}/sessions/{contextId}/tools/{name}
```

The personal agent sees user-side tools. The CS agent sees bank-side tools.

Use real values only. Never fill placeholders such as:

```text
customer_name="User"
phone="unknown"
account_id="abc123"
```

Ask for missing information instead.

## Timeouts

The harness timeout budget is strict:

```text
agent turn: 5 minutes
whole task: 10 minutes
```

Implications:

```text
- Keep tool calls minimal.
- Do not run external web search in the scored path.
- Use Redis and local KB first.
- Avoid long multi-turn philosophical explanations.
- Retry only when the failure is recoverable and safe.
```

## Scoring implication

Final scoring rewards three pairings:

```text
50%: our personal-agent + our cs-agent
25%: our personal-agent + held-out cs-agent
25%: held-out personal-agent + our cs-agent
```

Therefore each agent must be independently interoperable.

Do not make personal-agent depend on a private response format that only our cs-agent returns. Do not make cs-agent depend on private prompts or hidden conventions from our personal-agent.
