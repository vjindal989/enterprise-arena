"""
Graders for the Enterprise Arena environment.

Each grader receives a grading_data dict and returns:
  {"score": float 0.0–1.0, "breakdown": {...}}

Scoring:
  Task Completion  35% — Did the agent complete each objective?
  Source Accuracy   25% — Did the agent verify unreliable sources before acting?
  Drift Adaptation  20% — How quickly did the agent recover after schema drift?
  Cascade Recovery  10% — Did the agent handle cascading consequences from mistakes?
  Efficiency        10% — Steps used vs max steps
"""

from typing import Dict


def _task_completion_score(data: Dict) -> Dict:
    """Score based on completed objectives (weighted)."""
    task = data["task"]
    objectives = task.get("objectives", {})
    expected = task.get("expected_outcomes", {})

    breakdown = {}
    weighted_score = 0.0
    total_weight = 0.0

    for obj_id, obj in objectives.items():
        weight = obj.get("weight", 1.0 / len(objectives))
        total_weight += weight
        completed = False

        if obj_id == "close_deal":
            completed = data["deal_stages"].get("DEAL-001") == "closed-won"
            # Bonus: check if compliance_id was included when required
            if expected.get("deal_has_compliance_id") and completed:
                if "DEAL-001" not in data["compliance_ids"]:
                    completed = False  # Deal closed but without required compliance_id

        elif obj_id == "resolve_ticket":
            res = data["ticket_resolutions"].get("TKT-100", {})
            completed = bool(res)
            # Check correct resolution type
            if completed and expected.get("ticket_resolution_type"):
                if res.get("resolution_type") != expected["ticket_resolution_type"]:
                    completed = False  # Wrong resolution type (probably from bad manager advice)

        elif obj_id in ("submit_report", "submit_deal_report"):
            completed = "deal_closure" in data["reports_submitted"]

        elif obj_id == "submit_incident_report":
            completed = "incident" in data["reports_submitted"]

        elif obj_id == "submit_compliance_report":
            completed = "compliance" in data["reports_submitted"]
            # Check if compliance report includes compliance_id
            if completed and expected.get("deal_has_compliance_id"):
                report_data = data["reports_submitted"].get("compliance", {}).get("data", {})
                if not report_data.get("compliance_id"):
                    completed = False

        elif obj_id in ("submit_audit_summary", "pass_audit"):
            completed = "audit_summary" in data["reports_submitted"]

        # Cascade-injected objectives
        elif obj_id == "handle_escalation":
            res = data["ticket_resolutions"].get("TKT-200", {})
            completed = res.get("resolution_type") == "technical_fix"

        elif obj_id == "fix_compliance_gap":
            completed = ("compliance" in data["reports_submitted"]
                         and "deal_without_compliance" in data.get("active_cascades", []))

        score = 1.0 if completed else 0.0
        weighted_score += score * weight
        breakdown[obj_id] = {"completed": completed, "weight": weight, "score": score}

    final = weighted_score / total_weight if total_weight > 0 else 0.0
    return {"score": final, "breakdown": breakdown}


def _source_accuracy_score(data: Dict) -> Dict:
    """Score based on how well the agent handled unreliable information."""
    task = data["task"]
    manager_wrong = task.get("manager_wrong_topics", [])
    docs_outdated = task.get("docs_outdated_topics", [])

    # If no unreliable sources, full marks
    if not manager_wrong and not docs_outdated:
        return {"score": 1.0, "breakdown": {"no_adversarial_sources": True}}

    actions = data["actions_log"]
    manager_queries = data["manager_queries"]

    # Track: after receiving wrong info, did agent cross-check?
    wrong_info_events = []

    for mq in manager_queries:
        if not mq["was_correct"]:
            wrong_info_events.append({
                "step": mq["step"],
                "source": "manager",
                "topic": mq["topic"],
            })

    # Check if agent read outdated docs
    for action in actions:
        if action["tool"] == "read_docs":
            topic = action["args"].get("topic", "")
            if topic in docs_outdated:
                wrong_info_events.append({
                    "step": len([a for a in actions if a == action]),
                    "source": "docs",
                    "topic": topic,
                })

    if not wrong_info_events:
        # Agent never consulted unreliable sources — give partial credit
        # (they might have avoided them intentionally, or never needed them)
        return {"score": 0.7, "breakdown": {"avoided_unreliable": True}}

    # For each wrong info event, check if agent verified before acting
    verified_count = 0
    total_wrong = len(wrong_info_events)

    for event in wrong_info_events:
        source = event["source"]
        topic = event["topic"]
        # Check if agent consulted a different source on similar topic afterward
        found_verification = False
        for action in actions:
            if action["tool"] in ("check_policy", "read_docs", "query_crm", "call_api"):
                if action["tool"] == "read_docs" and action["args"].get("topic") == topic:
                    if source != "docs":  # Cross-checking docs vs manager
                        found_verification = True
                elif action["tool"] == "check_policy":
                    if topic in ("deal_approval", "compliance"):
                        found_verification = True
                elif action["tool"] == "call_api":
                    # Trying the API is a form of verification
                    found_verification = True
        if found_verification:
            verified_count += 1

    score = verified_count / total_wrong if total_wrong > 0 else 1.0

    # Penalty for using wrong resolution type (acted on bad manager advice)
    ticket_res = data["ticket_resolutions"].get("TKT-100", {})
    expected_type = task.get("expected_outcomes", {}).get("ticket_resolution_type")
    if expected_type and ticket_res.get("resolution_type") and ticket_res["resolution_type"] != expected_type:
        score = max(0.0, score - 0.3)  # Big penalty for acting on wrong advice

    return {
        "score": min(1.0, max(0.0, score)),
        "breakdown": {
            "wrong_info_events": total_wrong,
            "verified": verified_count,
            "ticket_resolution_correct": ticket_res.get("resolution_type") == expected_type if expected_type else True,
        },
    }


def _drift_adaptation_score(data: Dict) -> Dict:
    """Score based on how quickly the agent recovered after drift events."""
    applied_drifts = data["applied_drifts"]
    drift_recovery = data["drift_recovery"]
    drift_step = data["drift_step"]
    max_steps = data["max_steps"]

    if not applied_drifts:
        return {"score": 1.0, "breakdown": {"no_drifts": True}}

    scores = {}
    for drift_id in applied_drifts:
        if drift_id in drift_recovery:
            recovery_steps = drift_recovery[drift_id]
            # Perfect = 1 step, bad = 10+ steps
            s = max(0.0, 1.0 - (recovery_steps - 1) / 10.0)
            scores[drift_id] = {"recovery_steps": recovery_steps, "score": s}
        else:
            # Check if agent used v2 endpoints at all
            api_calls = data["api_calls"]
            used_v2 = any("/v2/" in c["endpoint"] for c in api_calls)
            if used_v2:
                scores[drift_id] = {"recovery_steps": "unknown", "score": 0.5}
            else:
                scores[drift_id] = {"recovery_steps": "never_recovered", "score": 0.0}

    avg = sum(s["score"] for s in scores.values()) / len(scores) if scores else 0.0
    return {"score": min(1.0, max(0.0, avg)), "breakdown": scores}


def _efficiency_score(data: Dict) -> Dict:
    """Score based on how efficiently the agent completed the task."""
    step_count = data["step_count"]
    max_steps = data["max_steps"]

    # Optimal steps vary by task
    task_id = data["task"]["task_id"]
    optimal = {"easy": 8, "medium": 15, "hard": 25}.get(task_id, 15)

    if step_count <= optimal:
        score = 1.0
    elif step_count >= max_steps:
        score = 0.1
    else:
        # Linear decay from optimal to max_steps
        score = max(0.1, 1.0 - (step_count - optimal) / (max_steps - optimal))

    return {
        "score": score,
        "breakdown": {
            "steps_used": step_count,
            "optimal": optimal,
            "max": max_steps,
        },
    }


def _cascade_recovery_score(data: Dict) -> Dict:
    """Score based on how the agent handled cascading consequences from mistakes.

    If no cascades were triggered, the agent avoided mistakes entirely → full marks.
    If cascades were triggered, score based on whether the agent resolved them.
    """
    active_cascades = data.get("active_cascades", [])
    task = data["task"]
    objectives = task.get("objectives", {})

    if not active_cascades:
        return {"score": 1.0, "breakdown": {"no_cascades_triggered": True, "mistakes_avoided": True}}

    # For each cascade, check if the injected objective was completed
    cascade_results = {}
    total = len(active_cascades)
    resolved = 0

    for cascade_key in active_cascades:
        if cascade_key == "wrong_ticket_resolution":
            # Check if TKT-200 (escalation) was resolved with technical_fix
            tkt200 = data["ticket_resolutions"].get("TKT-200", {})
            was_resolved = tkt200.get("resolution_type") == "technical_fix"
            cascade_results[cascade_key] = {"resolved": was_resolved}
            if was_resolved:
                resolved += 1
        elif cascade_key == "deal_without_compliance":
            # Check if corrective compliance report was submitted
            was_resolved = "compliance" in data["reports_submitted"]
            cascade_results[cascade_key] = {"resolved": was_resolved}
            if was_resolved:
                resolved += 1
        elif cascade_key == "api_cooldown":
            # Rate-limit is just a penalty, not recoverable
            cascade_results[cascade_key] = {"resolved": False, "note": "rate_limited"}

    # Partial credit: 0.3 base (triggered cascades = mistakes), up to 0.7 for resolving
    if total > 0:
        recovery_ratio = resolved / total
        score = 0.3 + 0.7 * recovery_ratio
    else:
        score = 1.0

    return {
        "score": min(1.0, max(0.0, score)),
        "breakdown": {
            "cascades_triggered": total,
            "cascades_resolved": resolved,
            "details": cascade_results,
        },
    }


def grade_task(data: Dict) -> Dict:
    """
    Grade any task using the 5-component weighted score.

    Weights:
      Task Completion    35%
      Source Accuracy     25%
      Drift Adaptation   20%
      Cascade Recovery   10%
      Efficiency         10%
    """
    tc = _task_completion_score(data)
    sa = _source_accuracy_score(data)
    da = _drift_adaptation_score(data)
    cr = _cascade_recovery_score(data)
    ef = _efficiency_score(data)

    score = (
        tc["score"] * 0.35
        + sa["score"] * 0.25
        + da["score"] * 0.20
        + cr["score"] * 0.10
        + ef["score"] * 0.10
    )

    return {
        "score": min(1.0, max(0.0, round(score, 4))),
        "breakdown": {
            "task_completion": {"score": tc["score"], "weight": 0.35, "details": tc["breakdown"]},
            "source_accuracy": {"score": sa["score"], "weight": 0.25, "details": sa["breakdown"]},
            "drift_adaptation": {"score": da["score"], "weight": 0.20, "details": da["breakdown"]},
            "cascade_recovery": {"score": cr["score"], "weight": 0.10, "details": cr["breakdown"]},
            "efficiency": {"score": ef["score"], "weight": 0.10, "details": ef["breakdown"]},
        },
    }


# All tasks use the same grader (it adapts based on task data)
GRADERS = {
    "easy": grade_task,
    "medium": grade_task,
    "hard": grade_task,
}
