# Adaptive Enterprise Arena: Teaching AI Agents to Navigate Chaos

**TL;DR:** We built an OpenEnv environment where AI agents must complete enterprise workflows while dealing with schema drift, adversarial NPCs, and cascading consequences. A naive agent scores 0.63 — after training on expert trajectories, it reaches 0.87 (+24% improvement).

---

## The Problem: Enterprise AI Is Fragile

Most LLM benchmarks test agents in static worlds. But real enterprise environments are messy:

- **APIs change** — The endpoint you called yesterday returns 404 today
- **People give outdated advice** — Your manager hasn't read the migration docs
- **Documentation lags behind** — The wiki still shows v1 examples
- **Mistakes cascade** — A wrong API call → bad data → failed compliance report → audit failure

We wanted to build an environment that captures this chaos and measures whether agents can **adapt**.

## The Environment: Enterprise Arena

The agent plays an enterprise employee at "Nexus Corp" who must complete multi-step business workflows:

| Task | What the Agent Does | What Goes Wrong |
|------|-------------------|-----------------|
| **Easy** | Close a deal + submit report | API migrates v1→v2 mid-task |
| **Medium** | Close deal + resolve support ticket | API drifts + manager gives wrong advice on ticket resolution |
| **Hard** | Full pipeline with compliance audit | 3 schema drifts + adversarial manager + outdated documentation |

### 9 Tools, 5 Information Sources

The agent has 9 MCP tools to interact with the enterprise:

- `query_crm` — Always accurate (ground truth)
- `check_policy` — Authoritative, but policies can change mid-episode
- `read_docs` — May be outdated without warning
- `ask_manager` — May give confidently wrong advice
- `call_api` — Endpoints can deprecate, schemas can change

The core skill the agent must learn: **not all sources are equally trustworthy, and the right source changes over time.**

### Schema Drift

At predefined step thresholds, drift events fire:
1. **API Rename**: `/v1/deals/update` → deprecated, `/v2/deals/update` activated
2. **Required Field**: `/v2/deals/update` now requires `compliance_id`
3. **Policy Change**: Deal approval threshold drops from $50k to $25k

A naive agent that memorized the API schema will hit 404s. A smart agent reads the error message, checks docs, and adapts.

### Adversarial Actors

The manager responds based on keyword matching to your question. On certain topics (configured per task), the manager gives plausible but wrong advice:

> **You:** "How should I resolve TKT-100?"
> **Manager (wrong):** "Just process a refund. Data export issues are usually client-side."
> **Policy (correct):** "For data-related issues, verify the root cause before applying fixes."

A naive agent follows the manager. A smart agent cross-checks against policy and CRM data.

## The Scoring: 4-Component Reward

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| Task Completion | 40% | Did you finish all objectives correctly? |
| Source Accuracy | 30% | Did you verify unreliable sources before acting? |
| Drift Adaptation | 20% | How quickly did you recover after schema changes? |
| Efficiency | 10% | Steps used vs optimal |

This reward structure means an agent can't just brute-force completion — it must demonstrate **intelligent information gathering**.

## Results: Naive vs. Smart Agent

We ran two scripted strategies across all tasks:

| Task | Naive (Pre-Training) | Smart (Post-Training) | Improvement |
|------|---------------------|----------------------|-------------|
| Easy | 0.80 | 0.90 | +0.10 |
| Medium | 0.59 | 0.90 | +0.31 |
| Hard | 0.51 | 0.82 | +0.31 |
| **Average** | **0.63** | **0.87** | **+0.24** |

### What the Naive Agent Gets Wrong

1. **Follows bad manager advice** → Uses "refund" instead of "technical_fix" for tickets
2. **Retries deprecated endpoints** → Hits v1 404 three times before trying v2
3. **Skips compliance steps** → Doesn't generate compliance_id on hard task
4. **Doesn't cross-check** → Takes first answer as truth

### What the Smart Agent Does Right

1. **Cross-verifies** → Checks policy after manager says "just refund"
2. **Reads error messages** → 404 says "migrated to v2", immediately switches
3. **Follows the compliance chain** → Generates compliance_id, includes in deal + report
4. **Consults multiple sources** → CRM (truth) + docs + policy before acting

## Training: LoRA Fine-Tuning on Expert Trajectories

We collected expert trajectories (the "smart" strategy) and fine-tuned Llama-3.2-1B-Instruct using:

- **Unsloth** for 2x faster LoRA training
- **TRL's SFTTrainer** with ChatML-formatted conversations
- **4-bit quantization** (runs on free Colab T4)
- 3 epochs, lr=2e-4, LoRA r=16

The training teaches the model three key behaviors:
1. Always read docs/policy before calling APIs
2. When an API returns 404, check for migration
3. Cross-check manager advice against policy before acting on tickets

## Architecture

Built on the [OpenEnv](https://github.com/meta-pytorch/OpenEnv) framework:
- `MCPEnvironment` base class with `FastMCP` tools
- Custom HTTP routes with singleton environment for stateful episodes
- Deterministic grading with 4-component scoring
- WebSocket support for MCP Playground
- Fully validated: 6/6 `openenv validate` checks, 29 unit tests

## Try It

- **Live Space**: [Vjindal26/enterprise-arena](https://huggingface.co/spaces/Vjindal26/enterprise-arena)
- **GitHub**: [vjindal989/enterprise-arena](https://github.com/vjindal989/enterprise-arena)
- **Train on Colab**: Clone the repo, run `python train_colab.py`

---

*Built for the OpenEnv Hackathon Round 2. The environment is deterministic and fully reproducible.*
