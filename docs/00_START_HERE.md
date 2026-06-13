# A2A Bank Resolution Engine — Start Here

This document pack replaces the earlier `ProcureNet` / procurement marketplace plan.

The actual Track 1 template is a fixed two-agent customer-service benchmark:

```text
Simulated user / harness
        ↓ A2A message/send
personal-agent :9001
        ↓ A2A via CS_AGENT_URL
cs-agent :9002
        ↓ Redis RAG + bank-side env tools
Redis
```

The goal is not to invent a new product domain. The goal is to make the two required agents solve bank customer-service tasks reliably, while staying interoperable with held-out agents.

## Working name

**A2A Bank Resolution Engine**

One-line pitch:

> A robust personal banking assistant and bank customer-service agent pair that resolve simulated banking tasks through structured A2A coordination, policy retrieval, tool execution, and strict context isolation.

## Clone setup

Clone the organiser template and harness side-by-side:

```bash
mkdir a2a-hackathon-workspace
cd a2a-hackathon-workspace

git clone https://github.com/a2anet/a2a-hackathon-template bank-resolution-agent
git clone https://github.com/a2anet/a2a-hackathon harness
```

Copy this doc pack into the cloned template repo:

```bash
cd bank-resolution-agent
mkdir -p docs
# Copy these markdown files into ./docs/
```

Configure the template:

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY / Vertex settings as required by the organisers.
```

Run the agents:

```bash
docker compose up --build
```

In another terminal, run smoke from the harness repo:

```bash
cd ../harness
export GOOGLE_API_KEY=<same key as template .env>

uv run a2a-hack smoke \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002
```

Then run train:

```bash
uv run a2a-hack run \
  --personal-url http://localhost:9001 \
  --cs-url http://localhost:9002 \
  --tasks train \
  --save-to results/dev \
  --auto-resume

uv run tau2 view results/dev
```

## What to do first

Do these in order:

1. Run the template unchanged and save baseline train results.
2. Improve `personal_agent/agent.py` prompt.
3. Improve `cs_agent/agent.py` prompt and response format.
4. Add a hybrid RAG helper in `cs_agent/rag_tools.py`.
5. Iterate on failures from `tau2 view`.
6. Add optional Redis context ledger only after prompts and RAG are stable.

Do not start with a custom A2A executor, a new framework, Linkup integration, or product UI. The scoring path is the benchmark harness.

## Definition of done for the first coding session

By the end of the first session:

```text
[ ] Repo cloned.
[ ] .env configured.
[ ] docker compose up --build succeeds.
[ ] smoke passes without contextId errors.
[ ] baseline train result saved.
[ ] first prompt-only improvement committed.
[ ] second train run compared against baseline.
```
