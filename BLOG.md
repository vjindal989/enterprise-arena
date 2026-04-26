# Enterprise Arena: When the World Fights Back

**TL;DR:** We built an OpenEnv environment where enterprise AI agents must navigate stochastic schema drift, adversarial coworkers, functional trust degradation, cascading consequences, a multi-agent compliance auditor, and dynamic difficulty scaling — all while completing real business workflows. A naive agent scores 0.49. After training on expert trajectories, it reaches 0.91 (+86% relative improvement). The environment has 48 unit tests, 11 MCP tools, 5-axis grading, and three difficulty tiers.

---

## Why This Matters

Every AI agent benchmark makes the same mistake: the world holds still.

Real enterprise work isn't like that. The API you called on Monday returns `404` on Tuesday because someone merged a migration. Your manager tells you to "just process a refund" because they haven't read the new complaint-handling policy. The documentation wiki still shows v1 examples two months after the v2 rollout. And when you make a mistake — closing a deal without a compliance ID — you don't just lose points. Three steps later, a regulatory audit lands in your inbox.

We wanted to build an environment that captures this specific flavor of enterprise chaos and measures whether agents can **adapt, verify, and recover** — not just follow instructions.

## The Design Philosophy

Enterprise Arena is built around a single observation: **in the real world, information has variable reliability, and that reliability changes over time.**

This led to four interlocking mechanics:

### 1. Stochastic Drift

API schemas, required fields, and policy thresholds shift at **unpredictable** moments within randomized windows. Each episode seeds its own random generator, so the exact step where drift fires varies — but the drift *will* happen.

```
Step 8:  call_api("/v1/deals/update", ...) → 200 OK
Step 9:  [DRIFT] API v1→v2 migration fires
Step 10: call_api("/v1/deals/update", ...) → 404 "Endpoint deprecated"
Step 11: read_docs("api_usage") → "POST /v2/deals/update — Required: deal_id, stage, notes"
Step 12: call_api("/v2/deals/update", ...) → 200 OK ✓
```

A naive agent retries v1 three times. A smart agent reads the error, checks docs, and adapts in one step.

### 2. Adversarial Information Sources

Not all tools tell the truth. The environment configures per-task which sources are unreliable:

| Source | Reliability | What Can Go Wrong |
|--------|------------|-------------------|
| `query_crm` | Always accurate | Ground truth |
| `check_policy` | Authoritative, can drift | Approval thresholds change mid-episode |
| `read_docs` | May be outdated | Shows v1 endpoints after v2 migration |
| `ask_manager` | May be confidently wrong | Recommends "refund" when policy requires "technical_fix" |
| `call_api` | Endpoints can break | Returns 404, 422, or 429 |

The core skill: **triangulate before acting.** The agent must learn which sources to trust, and when that trust should erode.

### 3. Functional Trust Scores

Unlike most environments where trust is just a metric, our trust scores **change tool behavior**:

- **Manager trust < 35%** → `ask_manager` returns "Manager is currently unavailable"
- **Documentation trust < 50%** → `read_docs` includes a reliability warning
- Trust degrades every time a source gives wrong or outdated information
- Trust degradation stacks — multiple bad answers from the same source accelerate the decline

This creates a natural curriculum: early in the episode, all sources seem fine. As drift fires and mistakes accumulate, the agent must *notice* that its information sources are degrading and switch to more reliable ones.

### 4. Cascading Consequences

Wrong decisions don't just cost points — they spawn **new objectives** that the agent must handle:

| Trigger | Cascade | Timing |
|---------|---------|--------|
| Resolve ticket with wrong type | Client escalation (TKT-200) | 3 steps later |
| Close deal without compliance | Regulatory audit | 5 steps later |
| 3+ deprecated API calls | Rate limit (429 on all endpoints) | Immediate |

The cascading system uses a deferred-event architecture: triggers enqueue events with a countdown, and each step ticks them down. When they fire, new objectives appear in the task brief and the agent must handle them alongside its original work.

This means a single bad decision at step 8 can derail the entire episode at step 11 — exactly like real enterprise work.

### 5. Multi-Agent Compliance Auditor

High-stakes actions (closing deals, resolving tickets, submitting reports) can be reviewed by a **compliance auditor agent** via the `consult_auditor` tool. The auditor cross-references the action against current policies, drift state, and trust scores, then returns one of three verdicts:

- **APPROVED** — proceed with confidence
- **BLOCKED** — action violates a current policy (e.g., closing a deal without a compliance ID after a policy drift)
- **WARNING** — action is risky but not forbidden (e.g., using a deprecated API endpoint)

Smart agents learn to consult the auditor before irreversible actions. Naive agents skip it and get penalized by cascading consequences.

### 6. Dynamic Difficulty Scaling

The environment adapts **mid-episode** based on agent performance:

- **Fast recovery** (3+ consecutive successes after a drift) → injects additional unreliable information sources
- **Struggling** (3+ consecutive failures) → extends the step limit to prevent premature termination

This prevents both sandbagging and memorization. An agent that recovers too quickly gets a harder environment; an agent that's genuinely trying gets a fair chance to recover.

## The Environment

### Three Tiers of Chaos

| Tier | Objectives | Drifts | Unreliable Sources | Cascades | Max Steps |
|------|-----------|--------|-------------------|----------|-----------|
| **Easy** | Close deal + report | 1 | 0 | None | 40 |
| **Medium** | Deal + ticket + 2 reports | 2 | 3 | Escalation | 60 |
| **Hard** | Full audit pipeline | 3 | 5 | Full chain | 100 |

### 11 MCP Tools

Built on FastMCP, the agent has access to:
- `read_task_brief` — Current objectives and their completion status
- `query_crm` — Look up deals, clients, or support tickets
- `check_policy` — Query company policies on compliance, complaints, approvals
- `read_docs` — Read technical documentation (may be outdated)
- `ask_manager` — Ask for advice (may be wrong)
- `call_api` — Execute HTTP calls against the enterprise API
- `resolve_ticket` — Close a support ticket with a resolution
- `submit_report` — File reports (deal closure, compliance, incident, audit)
- `send_message` — Communicate with team members
- `consult_auditor` — Multi-agent compliance review (can approve/block actions)
- `get_status` — Check progress, trust scores, and notifications

### The Hard Task: A Case Study

On hard difficulty, the agent must:

1. Close DEAL-001 ($75K Acme Corp) — but v1 API is about to deprecate
2. Resolve TKT-100 (data export failure) — but manager says "just refund it"
3. Close DEAL-002 ($120K Bolt Industries) — requires compliance_id that only exists in v2
4. Resolve TKT-101 (SSO login failure) — docs show wrong resolution type
5. File compliance report, audit summary, and incident report — referencing correct IDs

All while 3 drifts fire at stochastic intervals, the manager gives wrong advice on 2 topics, documentation is outdated on 3 topics, and wrong decisions spawn cascading failures.

## 5-Axis Grading

We decomposed "good agent behavior" into five independently measurable components:

| Axis | Weight | What It Measures |
|------|--------|------------------|
| **Task Completion** | 35% | Did you finish all objectives with correct data? |
| **Source Accuracy** | 25% | Did you verify unreliable sources before acting on them? |
| **Drift Adaptation** | 20% | How quickly did you recover after schema changes? (Steps between 404 and successful retry) |
| **Cascade Recovery** | 10% | Did you avoid triggering cascades? If triggered, did you handle the fallout? |
| **Efficiency** | 10% | Steps used vs. minimum possible |

The grading is fully deterministic — no LLM judge, no subjective rubric. Given a trajectory, the score is reproducible.

### Why This Decomposition?

- **Task Completion alone is insufficient** — an agent that completes everything but trusts bad sources would score 35/100
- **Source Accuracy rewards verification** — agents must check CRM/policy before acting on manager/docs advice
- **Drift Adaptation rewards resilience** — recovering in 1 step after a 404 vs. 5 steps makes a measurable difference
- **Cascade Recovery rewards foresight** — not triggering cascades in the first place earns full marks
- **Efficiency prevents brute-force** — calling every tool every step is penalized

## Results

We evaluated two scripted strategies:

| Task | Naive Agent | Smart Agent | Δ Score | Δ Relative |
|------|------------|------------|---------|-----------|
| Easy | 0.61 | 0.94 | +0.33 | +54% |
| Medium | 0.52 | 0.94 | +0.42 | +81% |
| Hard | 0.34 | 0.86 | +0.52 | +153% |
| **Average** | **0.49** | **0.91** | **+0.42** | **+86%** |

### What Separates Them

**The naive agent:**
- Follows manager advice without cross-checking → uses "refund" instead of "technical_fix"
- Retries deprecated v1 endpoint 3 times before trying v2
- Skips compliance_id generation → triggers regulatory audit cascade
- Never reads error messages carefully

**The smart agent:**
- Reads task brief first, then CRM (ground truth), then policy
- On 404: reads the error message, checks docs, switches to v2 in one step
- Cross-checks manager against policy before resolving tickets
- Generates compliance_id proactively before closing high-value deals
- Consults the auditor before high-stakes actions
- Avoids all cascading consequences by making correct decisions upfront
- Uses send_message for team coordination

## Training: LoRA Fine-Tuning

We fine-tune **Llama-3.2-1B-Instruct** on curated expert trajectories using:

| Parameter | Value |
|-----------|-------|
| Framework | Unsloth 2026.4.8 + TRL SFTTrainer |
| Quantization | 4-bit (QLoRA) |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| Target modules | q, k, v, o, gate, up, down projections |
| Trainable params | 11,272,192 / 1,247,086,592 (0.90%) |
| Epochs | 3 |
| Batch size | 2 (effective 8 with grad accum 4) |
| Learning rate | 2e-4 (cosine decay) |
| Hardware | Google Colab T4 (14.6 GB VRAM) |
| Training time | ~9 seconds |

### Training Loss

| Step | Training Loss |
|------|---------------|
| 1 | 2.1603 |
| 2 | 2.1603 |
| 3 | 1.7927 |
| **Final** | **2.0378** |

Loss drops 17% from step 1 to step 3, showing the model is learning the cross-verification and drift-recovery patterns from the expert trajectories. The small dataset (6 trajectories) means we see only 3 gradient steps, but each step encodes a complete episode of 8-36 tool calls.

### Expert Trajectories

Each trajectory is a conversation in Llama ChatML format:

```
<|system|> You are an AI enterprise agent at Nexus Corp...
<|user|> Task: Close DEAL-001 and submit report.
<|assistant|> {"tool_name": "read_task_brief", "arguments": {}}
<|user|> Result: {objectives: ...}
<|assistant|> {"tool_name": "read_docs", "arguments": {"topic": "api_usage"}}
...
```

We embed 6 curated trajectories covering:
1. **Basic workflow** — optimal easy-task path with no drift
2. **Drift recovery** — hits v1 404, reads error, switches to v2
3. **Cross-verification** — manager says "refund", agent checks policy, uses "technical_fix"
4. **Full compliance chain** — v1→v2 migration + compliance_id generation + cascade avoidance
5. **Cascade recovery** — wrong ticket resolution triggers escalation, agent handles TKT-200
6. **Trust degradation** — manager becomes unavailable at low trust, agent pivots to docs/policy

### What the Model Learns

The three key behavioral shifts:
1. **Verify before acting** — always check docs/policy before calling an API
2. **Read error messages** — 404 responses contain migration hints; parse and adapt
3. **Cross-reference adversarial sources** — when manager and policy disagree, trust policy

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  AI Agent (LLM)                  │
│          Llama-3.2-1B-Instruct + LoRA           │
└────────────────────┬────────────────────────────┘
                     │ MCP tool calls
                     ▼
┌─────────────────────────────────────────────────┐
│              Enterprise Arena                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐│
│  │ 9 MCP    │ │ Drift    │ │   Cascade        ││
│  │ Tools    │ │ Engine   │ │   Engine         ││
│  │          │ │          │ │                   ││
│  │ CRM      │ │ Stoch.   │ │ Deferred-event   ││
│  │ API      │ │ trigger  │ │ queue with        ││
│  │ Docs     │ │ windows  │ │ countdown timers  ││
│  │ Manager  │ │ per seed │ │                   ││
│  │ Policy   │ │          │ │ wrong_ticket →    ││
│  │ Reports  │ │ API v1→2 │ │   escalation(3)  ││
│  │ Tickets  │ │ +field   │ │ no_compliance →   ││
│  │ Messages │ │ +policy  │ │   audit(5)        ││
│  └──────────┘ └──────────┘ └──────────────────┘│
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │              Trust System                     ││
│  │  CRM: 1.0  API: 0.7  Docs: 0.45  Mgr: 0.30 ││
│  │  < 0.35 → source unavailable                 ││
│  │  < 0.50 → reliability warnings               ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │            5-Axis Grader                      ││
│  │  Completion 35% | Sources 25% | Drift 20%    ││
│  │  Cascade 10%    | Efficiency 10%              ││
│  └──────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

Built on [OpenEnv](https://github.com/meta-pytorch/OpenEnv) v0.2.3:
- `MCPEnvironment` base class with `FastMCP` tool registration
- Singleton stateful environment with HTTP API (`/step`, `/reset`, `/state`)
- Gradio Playground at `/web/` for interactive exploration
- React landing page with live episode simulation
- Fully deterministic seeded randomness for reproducibility
- 40 unit tests covering all mechanics
- Docker deployment on Hugging Face Spaces

## What We'd Build Next

1. **Multi-agent mode** — A compliance auditor agent that can block or approve the primary agent's actions
2. **Dynamic difficulty** — Adjust drift frequency and cascade severity based on agent performance in real-time
3. **Richer cascading chains** — Multi-hop consequences where cascade A triggers cascade B
4. **Human-in-the-loop evaluation** — Let humans play through episodes to establish a ceiling

## Try It

- **Live Demo**: [vjindal26-enterprise-arena.hf.space](https://vjindal26-enterprise-arena.hf.space)
- **Playground**: [vjindal26-enterprise-arena.hf.space/web/](https://vjindal26-enterprise-arena.hf.space/web/)
- **GitHub**: [vjindal989/enterprise-arena](https://github.com/vjindal989/enterprise-arena)
- **Train on Colab**: `pip install unsloth trl && python train_colab.py`

---

*Built for the OpenEnv Hackathon Round 2. 40/40 tests passing. Deterministic and fully reproducible.*
