"""
Baseline inference script for the Enterprise Arena environment.

Runs a single episode using an LLM (OpenAI-compatible API) and prints
structured [START] / [STEP] / [END] logs.

Usage:
  python inference.py --task easy --model meta-llama/Llama-3.1-8B-Instruct
"""

import argparse
import json
import os
import sys
import time

import requests

BASE_URL = os.getenv("ENV_URL", "http://localhost:8000")
HF_TOKEN = os.getenv("HF_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")

SYSTEM_PROMPT = """\
You are an AI enterprise agent at Nexus Corp. You interact with the environment
by calling tools. Each turn, respond with EXACTLY one JSON tool call:

{"tool_name": "<name>", "arguments": {<args>}}

Available tools:
- read_task_brief() — Start here. Get your objectives.
- query_crm(record_type, record_id?) — Query CRM. Types: deals, clients, tickets
- check_policy(topic) — Topics: deal_approval, complaint_handling, compliance
- ask_manager(question) — Ask manager (may be wrong, verify before acting)
- read_docs(topic) — Topics: api_usage, crm_guide, compliance_guide
- call_api(endpoint, method?, data?) — Call enterprise API endpoint
- submit_report(report_type, data?) — Types: deal_closure, incident, compliance, audit_summary
- resolve_ticket(ticket_id, resolution, resolution_type?) — Types: technical_fix, workaround, escalation, refund
- get_status() — Check progress and trust scores

STRATEGY:
1. Always start with read_task_brief
2. Gather info from multiple sources before acting
3. Cross-check manager advice against docs/policy
4. After API errors, check docs for updated endpoints
5. Use get_status to track progress
6. Submit all required reports

Respond ONLY with a single JSON tool call. No extra text.
"""


def call_llm(messages: list, model: str) -> str:
    """Call an OpenAI-compatible LLM API."""
    api_base = os.getenv("OPENAI_API_BASE", "https://api-inference.huggingface.co/v1")
    api_key = os.getenv("OPENAI_API_KEY", HF_TOKEN)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.1,
    }

    resp = requests.post(f"{api_base}/chat/completions", json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_tool_call(text: str) -> dict:
    """Extract a JSON tool call from LLM output."""
    text = text.strip()
    # Try direct JSON parse
    for start_char in ["{", "```json\n", "```\n"]:
        idx = text.find(start_char)
        if idx >= 0:
            candidate = text[idx:]
            candidate = candidate.strip("`").strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            try:
                obj = json.loads(candidate)
                if "tool_name" in obj:
                    return obj
            except json.JSONDecodeError:
                # Try to find matching brace
                brace_count = 0
                for i, c in enumerate(candidate):
                    if c == "{":
                        brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            try:
                                return json.loads(candidate[: i + 1])
                            except json.JSONDecodeError:
                                break
    return {"tool_name": "get_status", "arguments": {}}


def env_reset(task_id: str) -> dict:
    resp = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_step(tool_name: str, arguments: dict) -> dict:
    resp = requests.post(
        f"{BASE_URL}/step",
        json={"action": {"tool_name": tool_name, "arguments": arguments}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run_episode(task_id: str, model: str, max_steps: int = 50) -> dict:
    """Run a single episode and return results."""
    reset_resp = env_reset(task_id)
    obs = reset_resp.get("observation", {})

    print(f"[START] task={task_id} env=enterprise_arena model={model}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Environment reset. Task: {json.dumps(obs, indent=2)}\n\nCall your first tool:"},
    ]

    total_reward = 0.0
    step = 0
    done = False
    rewards = []

    while step < max_steps and not done:
        step += 1
        try:
            llm_output = call_llm(messages, model)
        except Exception as e:
            print(f"[STEP] step={step} action=llm_error reward=0 done=false error={e}")
            break

        tool_call = parse_tool_call(llm_output)
        tool_name = tool_call.get("tool_name", "get_status")
        arguments = tool_call.get("arguments", {})

        try:
            step_resp = env_step(tool_name, arguments)
        except Exception as e:
            print(f"[STEP] step={step} action={tool_name} reward=0 done=false error={e}")
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": f"Error calling {tool_name}: {e}. Try a different approach."})
            continue

        obs = step_resp.get("observation", {})
        reward = step_resp.get("reward", 0.0)
        done = step_resp.get("done", False)
        total_reward = reward
        rewards.append(reward)

        error_str = obs.get("error", obs.get("result", {}).get("error", "")) if isinstance(obs, dict) else ""

        print(f"[STEP] step={step} action={tool_name} reward={reward} done={done} error={error_str or 'none'}")

        messages.append({"role": "assistant", "content": llm_output})
        obs_summary = json.dumps(obs, default=str)
        if len(obs_summary) > 2000:
            obs_summary = obs_summary[:2000] + "..."
        messages.append({"role": "user", "content": f"Result:\n{obs_summary}\n\nCall your next tool (or get_status to check progress):"})

    final_score = obs.get("final_score", total_reward) if isinstance(obs, dict) else total_reward
    breakdown = obs.get("final_breakdown", {}) if isinstance(obs, dict) else {}

    print(f"[END] success={'true' if done else 'false'} steps={step} score={final_score} rewards={json.dumps(rewards[-5:])}")

    if breakdown:
        print(f"[BREAKDOWN] {json.dumps(breakdown, indent=2)}")

    return {
        "task_id": task_id,
        "steps": step,
        "score": final_score,
        "done": done,
        "rewards": rewards,
        "breakdown": breakdown,
    }


def main():
    parser = argparse.ArgumentParser(description="Enterprise Arena Baseline Inference")
    parser.add_argument("--task", default="easy", choices=["easy", "medium", "hard"])
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--all-tasks", action="store_true", help="Run all tasks")
    args = parser.parse_args()

    if args.all_tasks:
        results = {}
        for task_id in ["easy", "medium", "hard"]:
            print(f"\n{'='*60}")
            print(f"Running task: {task_id}")
            print(f"{'='*60}\n")
            results[task_id] = run_episode(task_id, args.model, args.max_steps)
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for tid, r in results.items():
            print(f"  {tid}: score={r['score']:.4f} steps={r['steps']} done={r['done']}")
        # Save results
        with open("baseline_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\nResults saved to baseline_results.json")
    else:
        run_episode(args.task, args.model, args.max_steps)


if __name__ == "__main__":
    main()
