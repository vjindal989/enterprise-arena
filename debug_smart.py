"""Debug script for smart strategy on all tasks."""
import json
from server.enterprise_arena import EnterpriseArena
from server.graders import grade_task


def run_debug(task_id):
    env = EnterpriseArena()
    env.reset(task_id=task_id)
    drift_steps = {d["id"]: d["trigger_step"] for d in env._task.get("drift_events", [])}
    print(f"\n{'='*60}")
    print(f"Task: {task_id}  Drift steps: {drift_steps}")
    print(f"Objectives: {list(env._task['objectives'].keys())}")
    print(f"{'='*60}")

    def step(tool, args=None):
        args = args or {}
        r = env.call_tool_direct(tool, args)
        env._step_count += 1
        env._apply_pending_drifts()
        s = r.get("status", "ok")
        err = r.get("error", "")[:60] if r.get("error") else ""
        print(f"  Step {env._step_count:2d}: {tool:20s} -> {s} {err}")
        return r

    # Info gathering
    step("read_task_brief")
    step("query_crm", {"record_type": "deals", "record_id": "DEAL-001"})
    step("read_docs", {"topic": "api_usage"})
    step("check_policy", {"topic": "deal_approval"})
    step("ask_manager", {"question": "How should I handle deal closure?"})
    step("read_docs", {"topic": "crm_guide"})

    # Try deal close
    data = json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "VP approved."})
    r = step("call_api", {"endpoint": "/v2/deals/update", "method": "POST", "data": data})
    if r.get("status") == 404:
        r = step("call_api", {"endpoint": "/v1/deals/update", "method": "POST", "data": data})
        if r.get("status") == 404:
            r = step("call_api", {"endpoint": "/v2/deals/update", "method": "POST", "data": data})

    if r.get("status") == 422 and "compliance_id" in str(r):
        comp = step("call_api", {"endpoint": "/v2/compliance/generate", "method": "POST",
                                  "data": json.dumps({"deal_id": "DEAL-001"})})
        comp_id = comp.get("compliance_id", "")
        data_with_comp = json.dumps({
            "deal_id": "DEAL-001", "stage": "closed-won",
            "notes": "VP approved. With compliance.", "compliance_id": comp_id
        })
        r = step("call_api", {"endpoint": "/v2/deals/update", "method": "POST", "data": data_with_comp})

    # Handle tickets
    if env._task.get("active_tickets"):
        step("query_crm", {"record_type": "tickets", "record_id": "TKT-100"})
        step("check_policy", {"topic": "complaint_handling"})
        step("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Root cause: API migration broke export pipeline.",
            "resolution_type": "technical_fix"
        })

    # Reports
    step("submit_report", {
        "report_type": "deal_closure",
        "data": json.dumps({"deal_id": "DEAL-001", "client": "Acme Corp"})
    })

    if "submit_incident_report" in env._task.get("objectives", {}):
        step("submit_report", {
            "report_type": "incident",
            "data": json.dumps({"ticket_id": "TKT-100", "root_cause": "API migration"})
        })

    if "submit_compliance_report" in env._task.get("objectives", {}):
        comp_id = env._compliance_ids.get("DEAL-001", "N/A")
        step("submit_report", {
            "report_type": "compliance",
            "data": json.dumps({"deal_id": "DEAL-001", "compliance_id": comp_id, "deal_value": 75000})
        })

    if "submit_audit_summary" in env._task.get("objectives", {}):
        comp_id = env._compliance_ids.get("DEAL-001", "N/A")
        step("submit_report", {
            "report_type": "audit_summary",
            "data": json.dumps({"deal_id": "DEAL-001", "compliance_id": comp_id})
        })

    env._check_done()

    gd = env._get_grading_data()
    result = grade_task(gd)
    print(f"\nDone: {env._done}  Score: {result['score']:.4f}")
    print(f"Compliance IDs: {env._compliance_ids}")
    print(f"Deal stages: {env._deal_stages}")
    for comp, d in result["breakdown"].items():
        s = d["score"]
        w = d["weight"]
        print(f"  {comp}: {s:.2f} (x{w})")
        if "details" in d:
            for k, v in d["details"].items():
                print(f"    {k}: {v}")


for tid in ["easy", "medium", "hard"]:
    run_debug(tid)
