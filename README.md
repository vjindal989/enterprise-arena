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

# Adaptive Enterprise Arena

An OpenEnv-compliant environment where AI agents navigate realistic enterprise
workflows under **schema drift**, **adversarial actors**, and **cascading
consequences**.

## What Makes It Hard

| Challenge | Description |
|-----------|-------------|
| **Schema Drift** | API endpoints migrate mid-episode (v1→v2). Old calls start failing. |
| **Adversarial Actors** | The manager gives outdated advice. Docs lag behind reality. |
| **Cascading Consequences** | Wrong API call → bad data → failed compliance report → audit failure. |
| **Trust Reasoning** | Agent must learn which sources to trust and when to cross-check. |

## Tasks

| Task | Objectives | Drifts | Adversarial | Max Steps |
|------|-----------|--------|-------------|-----------|
| **Easy** | Close deal + submit report | 1 (API rename) | None | 40 |
| **Medium** | Close deal + resolve ticket + reports | 2 (API + policy) | Manager wrong on 2 topics | 60 |
| **Hard** | Full pipeline + compliance + audit | 3 (API + field + policy) | Manager + outdated docs | 100 |

## Scoring (4-component reward)

- **Task Completion** (40%) — Did the agent finish all objectives?
- **Source Accuracy** (30%) — Did the agent verify unreliable sources before acting?
- **Drift Adaptation** (20%) — How quickly did the agent recover after schema changes?
- **Efficiency** (10%) — Steps used vs optimal

## Quick Start

```bash
# Install
pip install -e .

# Run locally
uvicorn server.app:app --port 8000

# Run with Docker
docker build -t enterprise-arena .
docker run -p 8000:8000 enterprise-arena
```

## API

```bash
# Reset (with task selection)
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}'

# Step (call a tool)
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action": {"tool_name": "read_task_brief", "arguments": {}}}'
```

## Tools Available to the Agent

| Tool | Description |
|------|-------------|
| `read_task_brief` | Get objectives and context |
| `query_crm` | Query CRM for deals, clients, tickets |
| `check_policy` | Check company policies (may update) |
| `ask_manager` | Ask manager for guidance (may be wrong) |
| `read_docs` | Read documentation (may be outdated) |
| `call_api` | Call enterprise API endpoints (may change) |
| `submit_report` | Submit business reports |
| `resolve_ticket` | Resolve support tickets |
| `get_status` | Check progress and trust scores |

## Architecture

Built on the [OpenEnv](https://github.com/meta-pytorch/OpenEnv) framework:
- `MCPEnvironment` base class with `FastMCP` tools
- Custom HTTP routes with singleton environment for stateful episodes
- Deterministic grading with 4-component scoring
- WebSocket support for MCP Playground
