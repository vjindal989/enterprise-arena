---
title: Enterprise Arena
emoji: 🏢
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8000
tags:
  - openenv
---

# Enterprise Arena

[![Tests](https://img.shields.io/badge/tests-40%2F40-brightgreen)]()
[![OpenEnv](https://img.shields.io/badge/OpenEnv-v0.2.3-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

An OpenEnv environment where AI agents navigate realistic enterprise workflows under **stochastic schema drift**, **adversarial information sources**, **functional trust degradation**, and **cascading consequences**.

**[Live Demo](https://vjindal26-enterprise-arena.hf.space)** · **[Playground](https://vjindal26-enterprise-arena.hf.space/web/)** · **[Blog](BLOG.md)**

## What Makes It Hard

| Challenge | Description |
|-----------|-------------|
| **Stochastic Drift** | API endpoints, required fields, and policy thresholds shift at unpredictable times within randomized windows |
| **Adversarial Actors** | Manager gives wrong advice. Documentation is outdated. Only CRM and policy are trustworthy |
| **Cascading Consequences** | Wrong ticket resolution → client escalation 3 steps later. Missing compliance → regulatory audit |
| **Functional Trust** | Trust scores change tool behavior. Low manager trust = unavailable. Low docs trust = reliability warnings |

## Tasks

| Task | Objectives | Drifts | Cascades | Max Steps |
|------|-----------|--------|----------|-----------|
| **Easy** | Close deal + report | 1 | None | 40 |
| **Medium** | Deal + ticket + 2 reports | 2 | Escalation | 60 |
| **Hard** | Full audit pipeline | 3 | Full chain | 100 |

## 5-Axis Grading

| Axis | Weight | Measures |
|------|--------|---------|
| Task Completion | 35% | All objectives completed with correct data |
| Source Accuracy | 25% | Verified unreliable sources before acting |
| Drift Adaptation | 20% | Recovery speed after schema changes |
| Cascade Recovery | 10% | Avoided or handled cascading failures |
| Efficiency | 10% | Steps used vs. optimal |

## Results

| Task | Naive | Smart | Δ |
|------|-------|-------|---|
| Easy | 0.80 | 0.90 | +12.5% |
| Medium | 0.59 | 0.90 | +52.5% |
| Hard | 0.51 | 0.82 | +60.8% |
| **Avg** | **0.63** | **0.87** | **+38.1%** |

## Quick Start

```bash
# Install
pip install -e .

# Run locally
ENABLE_WEB_INTERFACE=true uvicorn server.app:app --port 8000

# Run with Docker
docker build -t enterprise-arena .
docker run -p 8000:8000 enterprise-arena

# Run tests
pytest tests/test_env.py -v
```

## Training

```bash
# On Colab (free T4 GPU)
pip install unsloth trl datasets transformers accelerate bitsandbytes
python train_colab.py

# With custom trajectories
python train_colab.py --data trajectories.jsonl --epochs 3
```

## API

```bash
# Reset
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}'

# Step
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action": {"tool_name": "read_task_brief", "arguments": {}}}'
```

## 9 MCP Tools

| Tool | Reliability | Description |
|------|------------|-------------|
| `read_task_brief` | Always accurate | Current objectives and completion status |
| `query_crm` | Always accurate | Deals, clients, tickets (ground truth) |
| `check_policy` | Can drift | Company policies — thresholds may change |
| `ask_manager` | May be wrong | Advice — confidently incorrect on some topics |
| `read_docs` | May be outdated | Technical docs — lags behind API changes |
| `call_api` | Endpoints break | HTTP calls — 404, 422, 429 possible |
| `submit_report` | Always works | File business reports |
| `resolve_ticket` | Always works | Close support tickets |
| `send_message` | Always works | Team communication |

## Architecture

Built on [OpenEnv](https://github.com/meta-pytorch/OpenEnv) v0.2.3:
- `MCPEnvironment` base class with `FastMCP` tool registration
- Stochastic drift engine with seeded randomness
- Deferred-event cascade system with countdown timers
- Functional trust scores that modify tool behavior
- 5-component deterministic grader (no LLM judge)
- React landing page + Gradio Playground
- 40 unit tests, Docker deployment on HF Spaces
