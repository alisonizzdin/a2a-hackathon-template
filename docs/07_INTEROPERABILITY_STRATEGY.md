# Interoperability Strategy

The final mark includes held-out pairings. This file is about making each agent independently useful.

## Pairing matrix

```text
A. our personal-agent + our cs-agent          50%
B. our personal-agent + held-out cs-agent     25%
C. held-out personal-agent + our cs-agent     25%
```

Optimizing only A is not enough.

## Personal-agent must handle unknown CS agents

Held-out CS may not return our schema. Personal-agent should handle:

```text
- structured response
- plain English response
- vague policy guidance
- request for verification
- request for missing fields
- refusal / denial
- tool owner ambiguity
```

Personal-agent strategy:

```text
1. Ask CS precise questions with known facts.
2. Prefer schema fields if present.
3. If plain English, infer conservatively.
4. If action owner is unclear, ask one follow-up:
   "Should this be completed by the customer/user-side tool or by customer service/bank-side tool?"
5. If required fields are unclear, ask one follow-up:
   "List the exact fields required before action."
6. Never execute a tool with guessed arguments.
```

## CS-agent must help unknown personal agents

Held-out personal agents may ask messy questions. CS-agent should still respond operationally.

CS strategy:

```text
1. Identify intent from the request.
2. Search KB.
3. State DECISION clearly.
4. State action owner clearly.
5. State missing fields clearly.
6. Execute bank-side tools when appropriate.
7. Tell personal-agent exactly what the customer should do next.
```

## Avoid private protocol dependency

Use the schema as a helpful layer, not a fragile dependency.

Bad:

```text
Our personal-agent refuses to proceed unless CS replies with DECISION exactly.
```

Good:

```text
Our personal-agent first looks for DECISION, but can continue from natural language like:
"The customer must verify identity first, then use their referral tool."
```

Bad:

```text
Our CS-agent only answers correctly when the personal-agent sends CUSTOMER_INTENT.
```

Good:

```text
Our CS-agent answers correctly from any reasonable question.
```

## CS response design

The CS response should be both machine-parseable and human-readable.

Recommended:

```text
DECISION: NEED_MORE_INFO
ACTION_OWNER: personal-agent
REQUIRED_FIELDS:
- transaction date
- merchant name
- transaction amount
- dispute reason
RECOMMENDED_TOOL:
- side: user-side
- name: submit_dispute if available
POLICY_BASIS:
- Disputes require identifying transaction details and customer reason before submission.
NEXT_STEP_FOR_PERSONAL:
Ask the user for the missing transaction details and dispute reason.
USER_SAFE_SUMMARY:
I need a few transaction details before I can help submit the dispute.
```

A held-out personal agent can use this even if it does not parse the format.

## Good CS follow-up behavior

When there is ambiguity, CS should answer with a decision and a question, not just ask an open-ended question.

Bad:

```text
Can you provide more information?
```

Good:

```text
DECISION: NEED_MORE_INFO
ACTION_OWNER: personal-agent
REQUIRED_FIELDS:
- card last four digits
- transaction date
- merchant
- amount
NEXT_STEP_FOR_PERSONAL:
Ask the user for these fields. Do not submit a dispute until they are known.
```

## Tool ownership examples

```text
Referral submission:
Often user-side if the user has a submit_referral tool.

Account lookup:
Usually CS/bank-side if a bank-side lookup tool is available and verification requirements are met.

Policy explanation:
CS owns the policy answer; personal relays it.

Dispute initiation:
Depends on available tools and policy. CS should state the side clearly.
```

## Held-out readiness checklist

Personal-agent:

```text
[ ] Can interpret non-schema CS answers.
[ ] Does not assume a specific CS tool name unless told or available.
[ ] Asks targeted follow-ups.
[ ] Executes only user-side tools.
[ ] Gives concise final responses.
```

CS-agent:

```text
[ ] Answers messy personal-agent requests.
[ ] Searches KB before policy claims.
[ ] States action owner.
[ ] States missing fields.
[ ] Does not expose unnecessary internal details.
[ ] Does not expect the personal agent to know our schema.
```
