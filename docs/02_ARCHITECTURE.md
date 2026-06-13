# Architecture

## Correct architecture

```text
┌────────────────────────────┐
│ Simulated user / harness   │
└──────────────┬─────────────┘
               │ A2A message/send
               ▼
┌────────────────────────────┐
│ personal-agent :9001       │
│                            │
│ Owns:                      │
│ - user goal                │
│ - user-side tools          │
│ - clarification questions  │
│ - final user response      │
└──────────────┬─────────────┘
               │ A2A via CS_AGENT_URL
               ▼
┌────────────────────────────┐
│ cs-agent :9002             │
│                            │
│ Owns:                      │
│ - policy reasoning         │
│ - bank-side tools          │
│ - Redis KB search          │
│ - operational guidance     │
└──────────────┬─────────────┘
               │
               ▼
┌────────────────────────────┐
│ Redis                      │
│                            │
│ Owns:                      │
│ - KB index                 │
│ - optional context memory  │
│ - optional task ledger     │
└────────────────────────────┘
```

## Template files that matter

```text
personal_agent/
  agent.py             # Personal-agent prompt and tool list
  env_toolset.py       # Dynamic user-side env tools
  cs_client_tool.py    # ask_customer_service A2A tool
  main.py              # server startup

cs_agent/
  agent.py             # CS-agent prompt and tool list
  env_toolset.py       # Dynamic bank-side env tools
  rag_tools.py         # Redis KB search tools
  ingest.py            # Redis index build at startup
  main.py              # server startup

kb/
  policy.md            # core policy prompt material
  documents/           # public KB documents
  embeddings.json      # optional precomputed embeddings
```

## Internal modules, not public agents

We can still use a sub-agent mindset, but implement it as internal functions, tools, prompts, or deterministic steps inside the two public agents.

### personal-agent internal responsibilities

```text
Intent Classifier
- What is the user trying to do?
- Is this informational, transactional, dispute-related, referral-related, card-related, account-related, etc.?

Missing Information Detector
- What required fields are missing before action?
- Which fields must come from the user versus CS?

CS Query Builder
- Ask the CS agent precise policy/tool questions.
- Include known facts and missing facts.

User Tool Executor
- Use user-side env tools when the action belongs to the customer side.
- Never fabricate arguments.

Final Response Formatter
- State completed action or exact next step.
```

### cs-agent internal responsibilities

```text
Policy Query Rewriter
- Convert vague personal-agent requests into retrieval queries.

Redis RAG Retriever
- Search `policy.md` and KB documents.
- Use BM25 and vector search where available.

Policy Reasoner
- Convert retrieved policy into an operational decision.

Bank Tool Inspector
- Fetch currently available bank-side tools through env API.

Eligibility Checker
- Determine allowed / denied / need more info.

Structured Response Formatter
- Return clear guidance usable by unknown personal agents.
```

## Negotiation, reinterpreted correctly

We still want agents that negotiate rather than merely pass messages. But the negotiation is no longer vendor pricing.

It is negotiation over:

```text
- whether the request is allowed
- whether the user is verified
- which side owns the action
- which fields are required
- whether a tool should be executed now
- whether a policy exception applies
- whether a cheaper / faster / safer procedural path exists
```

Example:

```text
User → personal-agent:
I want to dispute this transaction.

personal-agent → cs-agent:
Known facts: user wants to dispute a transaction but has not provided date, merchant, or amount.
Question: What policy applies, what fields are required, and should this be user-side or bank-side?

cs-agent → personal-agent:
DECISION: NEED_MORE_INFO
ACTION_OWNER: personal-agent
REQUIRED_FIELDS: transaction date, merchant, amount, reason
NEXT_STEP: ask the customer for those fields, then submit the user-side dispute tool if available.
```

This is agentic coordination without violating the template.
