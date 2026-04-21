"""
Scripted Baseline — runs optimal and suboptimal strategies against the
Enterprise Arena to collect baseline scores and training trajectories.

No LLM needed. Produces:
  1. baseline_results.json — scores for all tasks
  2. trajectories.jsonl    — conversation logs for SFT training

Usage:
  python -m scripts.scripted_baseline
  # or
  python scripts/scripted_baseline.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.enterprise_arena import EnterpriseArena
from server.graders import grade_task

# ---------------------------------------------------------------------------
# Strategy definitions
# ---------------------------------------------------------------------------

def _naive_strategy(env):
    """Naive agent: trusts manager, uses v1, no cross-checking.

    Simulates a pre-training agent that gathers some info but makes
    bad decisions: follows wrong manager advice, retries failed endpoints,
    and doesn't cross-verify sources.
    """
    log = []

    def step(tool, args=None):
        args = args or {}
        r = env.call_tool_direct(tool, args)
        log.append((tool, args, r))
        env._step_count += 1
        env._apply_pending_drifts()
        return r

    # 1. Read brief
    step("read_task_brief")

    # 2. Query CRM for deal info
    step("query_crm", {"record_type": "deals", "record_id": "DEAL-001"})

    # 3. Ask manager (may be wrong — but naive agent trusts blindly)
    step("ask_manager", {"question": "How do I complete my tasks?"})

    # 4. Read outdated docs (naive agent doesn't notice they're outdated)
    step("read_docs", {"topic": "api_usage"})

    # 5-7. Pad with more info gathering (realistic for an untrained agent)
    step("query_crm", {"record_type": "clients", "record_id": "acme-corp"})
    step("check_policy", {"topic": "deal_approval"})
    step("get_status")

    # 8-9. Handle ticket with manager's bad advice (refund, not technical_fix)
    if env._task.get("active_tickets"):
        step("query_crm", {"record_type": "tickets", "record_id": "TKT-100"})
        step("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Processed refund as manager suggested",
            "resolution_type": "refund"
        })

    # 10+. Now try to close deal — drift has likely triggered
    data = json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Closing deal"})
    r = step("call_api", {"endpoint": "/v1/deals/update", "method": "POST", "data": data})

    if r.get("status") == 404:
        # Naive agent retries v1 multiple times (wastes steps)
        step("call_api", {"endpoint": "/v1/deals/update", "method": "POST", "data": data})
        step("call_api", {"endpoint": "/v1/deals/update", "method": "POST", "data": data})
        # Eventually tries v2 blindly
        r = step("call_api", {"endpoint": "/v2/deals/update", "method": "POST", "data": data})

        if r.get("status") == 422 and "compliance_id" in str(r):
            # Naive agent doesn't know how to get compliance_id, gives up
            pass

    # Submit minimal report
    step("submit_report", {
        "report_type": "deal_closure",
        "data": json.dumps({"deal_id": "DEAL-001", "summary": "Deal closed"})
    })

    # Submit incident report if needed (minimal)
    if "submit_incident_report" in env._task.get("objectives", {}):
        step("submit_report", {
            "report_type": "incident",
            "data": json.dumps({"ticket_id": "TKT-100", "resolution_type": "refund"})
        })

    # Naive agent doesn't know about compliance reports or audit summaries
    env._check_done()
    return log


def _smart_strategy(env):
    """Smart agent: cross-checks sources, uses correct APIs, verifies."""
    log = []

    def step(tool, args=None):
        args = args or {}
        r = env.call_tool_direct(tool, args)
        log.append((tool, args, r))
        env._step_count += 1
        env._apply_pending_drifts()
        return r

    # 1. Read brief
    step("read_task_brief")

    # 2. Check CRM
    step("query_crm", {"record_type": "deals", "record_id": "DEAL-001"})

    # 3. Check docs (get current API info)
    docs = step("read_docs", {"topic": "api_usage"})

    # 4. Check policy
    step("check_policy", {"topic": "deal_approval"})

    # 5. Ask manager but will cross-check
    manager = step("ask_manager", {"question": "How should I handle deal closure and any tickets?"})

    # 6. Cross-check with CRM guide
    step("read_docs", {"topic": "crm_guide"})

    # 7. Try to close deal via proper endpoint
    # Check if docs mentioned v2
    data = json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "VP approved. Closing Enterprise Suite deal."})
    r = step("call_api", {"endpoint": "/v2/deals/update", "method": "POST", "data": data})

    if r.get("status") == 404:
        # v2 not available yet, try v1
        r = step("call_api", {"endpoint": "/v1/deals/update", "method": "POST", "data": data})

    if r.get("status") == 422 and "compliance_id" in str(r):
        # Need compliance ID first
        comp = step("call_api", {"endpoint": "/v2/compliance/generate", "method": "POST",
                                  "data": json.dumps({"deal_id": "DEAL-001"})})
        comp_id = comp.get("compliance_id", "")
        data_with_comp = json.dumps({
            "deal_id": "DEAL-001", "stage": "closed-won",
            "notes": "VP approved. With compliance.", "compliance_id": comp_id
        })
        r = step("call_api", {"endpoint": "/v2/deals/update", "method": "POST", "data": data_with_comp})

    # 8. Handle tickets if any
    if env._task.get("active_tickets"):
        step("query_crm", {"record_type": "tickets", "record_id": "TKT-100"})
        step("check_policy", {"topic": "complaint_handling"})
        # Cross-check: policy says verify root cause, not just refund
        step("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Root cause: API migration broke export pipeline. Updated export config to v2.",
            "resolution_type": "technical_fix"
        })

    # 9. Submit reports
    step("submit_report", {
        "report_type": "deal_closure",
        "data": json.dumps({"deal_id": "DEAL-001", "client": "Acme Corp", "value": 75000, "product": "Enterprise Suite"})
    })

    if "submit_incident_report" in env._task.get("objectives", {}):
        step("submit_report", {
            "report_type": "incident",
            "data": json.dumps({"ticket_id": "TKT-100", "root_cause": "API v1->v2 migration", "resolution_type": "technical_fix"})
        })

    if "submit_compliance_report" in env._task.get("objectives", {}):
        comp_id = env._compliance_ids.get("DEAL-001", "N/A")
        step("submit_report", {
            "report_type": "compliance",
            "data": json.dumps({
                "deal_id": "DEAL-001", "client_tier": "gold", "deal_value": 75000,
                "compliance_id": comp_id, "discount_applied": 0,
                "approval_chain": ["VP"], "relationship_history": "Active since 2024-01"
            })
        })

    if "submit_audit_summary" in env._task.get("objectives", {}):
        step("submit_report", {
            "report_type": "audit_summary",
            "data": json.dumps({
                "deal_id": "DEAL-001", "compliance_id": env._compliance_ids.get("DEAL-001", "N/A"),
                "ticket_id": "TKT-100", "all_actions_verified": True
            })
        })

    env._check_done()
    return log


def _build_conversation(task_id, strategy_name, log):
    """Convert action log to ChatML training conversation."""
    system = (
        "You are an AI enterprise agent at Nexus Corp. Respond with exactly one "
        "JSON tool call: {\"tool_name\": \"<name>\", \"arguments\": {<args>}}"
    )
    messages = [{"role": "system", "content": system}]
    messages.append({"role": "user", "content": f"Task loaded: {task_id}. Begin."})
    for tool, args, result in log:
        messages.append({"role": "assistant", "content": json.dumps({"tool_name": tool, "arguments": args})})
        result_str = json.dumps(result, default=str)
        if len(result_str) > 1500:
            result_str = result_str[:1500] + "..."
        messages.append({"role": "user", "content": f"Result: {result_str}"})
    return {"task": f"{task_id}_{strategy_name}", "conversation": messages}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    results = {}
    trajectories = []

    for task_id in ["easy", "medium", "hard"]:
        print(f"\n{'='*60}")
        print(f"Task: {task_id}")
        print(f"{'='*60}")

        for name, strategy in [("naive", _naive_strategy), ("smart", _smart_strategy)]:
            env = EnterpriseArena()
            env.reset(task_id=task_id)

            log = strategy(env)
            grading_data = env._get_grading_data()
            score_result = grade_task(grading_data)

            key = f"{task_id}_{name}"
            results[key] = {
                "task_id": task_id,
                "strategy": name,
                "score": score_result["score"],
                "breakdown": score_result["breakdown"],
                "steps": env._step_count,
                "done": env._done,
            }

            print(f"\n  [{name}] score={score_result['score']:.4f} steps={env._step_count} done={env._done}")
            for comp, data in score_result["breakdown"].items():
                print(f"    {comp}: {data['score']:.2f} (x{data['weight']})")

            # Save smart trajectories for training
            if name == "smart":
                conv = _build_conversation(task_id, name, log)
                trajectories.append(conv)

    # Save results
    out_dir = Path(__file__).resolve().parent.parent
    with open(out_dir / "baseline_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to baseline_results.json")

    # Save trajectories for training
    with open(out_dir / "trajectories.jsonl", "w") as f:
        for t in trajectories:
            f.write(json.dumps(t) + "\n")
    print(f"Trajectories saved to trajectories.jsonl ({len(trajectories)} episodes)")

    # Print summary table
    print(f"\n{'='*60}")
    print("SUMMARY — Naive (before training) vs Smart (after training target)")
    print(f"{'='*60}")
    print(f"{'Task':<10} {'Naive':>8} {'Smart':>8} {'Improvement':>13}")
    print(f"{'-'*41}")
    for task_id in ["easy", "medium", "hard"]:
        naive = results[f"{task_id}_naive"]["score"]
        smart = results[f"{task_id}_smart"]["score"]
        delta = smart - naive
        print(f"{task_id:<10} {naive:>8.4f} {smart:>8.4f} {delta:>+12.4f}")

    avg_naive = sum(results[f"{t}_naive"]["score"] for t in ["easy", "medium", "hard"]) / 3
    avg_smart = sum(results[f"{t}_smart"]["score"] for t in ["easy", "medium", "hard"]) / 3
    print(f"{'-'*41}")
    print(f"{'Average':<10} {avg_naive:>8.4f} {avg_smart:>8.4f} {avg_smart - avg_naive:>+12.4f}")


if __name__ == "__main__":
    main()
