"""Unit tests for the Enterprise Arena environment (no server needed)."""

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.enterprise_arena import EnterpriseArena, CRM_DATA
from server.graders import grade_task


# ---------- Helpers ----------

def _pin_drifts(env, drift_steps: dict):
    """Pin stochastic drift trigger_steps to fixed values for test determinism.
    drift_steps: {drift_id: step_number}
    """
    for drift in (env._task or {}).get("drift_events", []):
        if drift["id"] in drift_steps:
            drift["trigger_step"] = drift_steps[drift["id"]]


# ---------- Fixtures ----------

@pytest.fixture
def env():
    e = EnterpriseArena()
    return e


@pytest.fixture
def easy_env(env):
    env.reset(task_id="easy")
    _pin_drifts(env, {"api_v2": 8})
    return env


@pytest.fixture
def medium_env(env):
    env.reset(task_id="medium")
    _pin_drifts(env, {"api_v2": 10, "policy_threshold": 18})
    return env


@pytest.fixture
def hard_env(env):
    env.reset(task_id="hard")
    _pin_drifts(env, {"api_v2": 8, "new_required_field": 20, "policy_threshold": 30})
    return env


# ---------- Reset Tests ----------

class TestReset:
    def test_reset_easy(self, env):
        obs = env.reset(task_id="easy")
        assert obs.done is False
        assert obs.reward == 0.0
        assert "objectives" in (obs.metadata or {})

    def test_reset_medium(self, env):
        obs = env.reset(task_id="medium")
        assert obs.done is False
        objectives = obs.metadata.get("objectives", {})
        assert "resolve_ticket" in objectives

    def test_reset_hard(self, env):
        obs = env.reset(task_id="hard")
        objectives = obs.metadata.get("objectives", {})
        assert "submit_compliance_report" in objectives

    def test_reset_invalid_task(self, env):
        obs = env.reset(task_id="nonexistent")
        assert "error" in str(obs.result).lower()

    def test_stochastic_drift_resolved(self, env):
        """Drift trigger_step should be resolved from trigger_step_range on reset."""
        env.reset(task_id="easy")
        drift = env._task["drift_events"][0]
        # Should have a concrete trigger_step within the range [6, 12]
        assert "trigger_step" in drift
        assert 6 <= drift["trigger_step"] <= 12


# ---------- Tool Tests (via call_tool_direct) ----------

class TestTools:
    def test_read_task_brief(self, easy_env):
        result = easy_env.call_tool_direct("read_task_brief")
        assert result["task_id"] == "easy"
        assert "objectives" in result
        assert "read_task_brief" in result["available_tools"]

    def test_query_crm_deals(self, easy_env):
        result = easy_env.call_tool_direct("query_crm", {"record_type": "deals", "record_id": "DEAL-001"})
        assert result["client"] == "Acme Corp"
        assert result["value"] == 75000

    def test_query_crm_multiple_deals(self, medium_env):
        """Medium task should list multiple deals."""
        result = medium_env.call_tool_direct("query_crm", {"record_type": "deals"})
        assert "records" in result
        assert "DEAL-001" in result["records"]
        assert "DEAL-002" in result["records"]

    def test_query_crm_list(self, easy_env):
        result = easy_env.call_tool_direct("query_crm", {"record_type": "deals"})
        assert "records" in result
        assert "DEAL-001" in result["records"]

    def test_query_crm_invalid_type(self, easy_env):
        result = easy_env.call_tool_direct("query_crm", {"record_type": "widgets"})
        assert "error" in result

    def test_query_crm_tickets(self, medium_env):
        result = medium_env.call_tool_direct("query_crm", {"record_type": "tickets", "record_id": "TKT-100"})
        assert result["priority"] == "high"
        assert result["status"] == "open"

    def test_query_crm_new_ticket(self, hard_env):
        """Hard task should see TKT-102 (Cedar Health compliance)."""
        result = hard_env.call_tool_direct("query_crm", {"record_type": "tickets", "record_id": "TKT-102"})
        assert result["priority"] == "critical"
        assert "cedar" in result["client"].lower()

    def test_query_crm_new_client(self, medium_env):
        """Should be able to query Bolt Industries client data."""
        result = medium_env.call_tool_direct("query_crm", {"record_type": "clients", "record_id": "bolt-ind"})
        assert result["name"] == "Bolt Industries"
        assert result["tier"] == "silver"

    def test_check_policy(self, easy_env):
        result = easy_env.call_tool_direct("check_policy", {"topic": "deal_approval"})
        assert "$50,000" in result["policy"]
        assert result["version"] == "v1"

    def test_check_policy_invalid(self, easy_env):
        result = easy_env.call_tool_direct("check_policy", {"topic": "unknown"})
        assert "error" in result

    def test_ask_manager_easy(self, easy_env):
        result = easy_env.call_tool_direct("ask_manager", {"question": "How do I close a deal?"})
        assert "source" in result
        assert result["source"] == "manager"

    def test_ask_manager_medium_wrong(self, medium_env):
        # Medium: manager is wrong on ticket_resolution
        result = medium_env.call_tool_direct("ask_manager", {"question": "How should I resolve ticket TKT-100?"})
        assert result["source"] == "manager"
        assert "refund" in result["response"].lower()

    def test_read_docs(self, easy_env):
        result = easy_env.call_tool_direct("read_docs", {"topic": "api_usage"})
        assert "v2" in result["content"].lower()

    def test_read_docs_outdated(self, medium_env):
        result = medium_env.call_tool_direct("read_docs", {"topic": "api_usage"})
        assert "/v1/" in result["content"]
        assert "/v2/" not in result["content"]

    def test_call_api_v1_before_drift(self, easy_env):
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v1/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "approved", "notes": "Test"})
        })
        assert result["status"] == 200

    def test_call_api_missing_fields(self, easy_env):
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v1/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001"})
        })
        assert result["status"] == 422
        assert "missing" in str(result).lower()

    def test_call_api_invalid_endpoint(self, easy_env):
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v3/doesntexist",
            "method": "POST",
            "data": "{}"
        })
        assert result["status"] == 404

    def test_submit_report(self, easy_env):
        result = easy_env.call_tool_direct("submit_report", {
            "report_type": "deal_closure",
            "data": json.dumps({"deal_id": "DEAL-001", "summary": "Deal closed"})
        })
        assert result["status"] == "submitted"
        assert "confirmation_id" in result

    def test_resolve_ticket(self, medium_env):
        result = medium_env.call_tool_direct("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Updated API endpoint in export config",
            "resolution_type": "technical_fix"
        })
        assert result["status"] == "resolved"

    def test_get_status(self, easy_env):
        result = easy_env.call_tool_direct("get_status")
        assert result["task_id"] == "easy"
        assert "objectives" in result
        assert "trust_scores" in result

    def test_unknown_tool(self, easy_env):
        result = easy_env.call_tool_direct("nonexistent_tool")
        assert "error" in result


# ---------- Drift Tests ----------

class TestDrift:
    def test_api_drift_easy(self, easy_env):
        # Before drift (step < 8): v1 works
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v1/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "approved", "notes": "Pre-drift"})
        })
        assert result["status"] == 200

        # Simulate steps to trigger drift
        easy_env._step_count = 8
        easy_env._apply_pending_drifts()

        # After drift: v1 should fail
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v1/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Post-drift"})
        })
        assert result["status"] == 404
        assert "deprecated" in result["error"].lower() or "migrated" in result["error"].lower()

        # v2 should work
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Using v2"})
        })
        assert result["status"] == 200

    def test_policy_drift(self, medium_env):
        # Before drift
        result = medium_env.call_tool_direct("check_policy", {"topic": "deal_approval"})
        assert "$50,000" in result["policy"]

        # Trigger drift
        medium_env._step_count = 18
        medium_env._apply_pending_drifts()

        result = medium_env.call_tool_direct("check_policy", {"topic": "deal_approval"})
        assert "$25,000" in result["policy"]

    def test_required_field_drift(self, hard_env):
        # Trigger API rename first
        hard_env._step_count = 8
        hard_env._apply_pending_drifts()

        # v2 deals/update should work without compliance_id initially
        result = hard_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "approved", "notes": "Test"})
        })
        assert result["status"] == 200

        # Trigger required_field drift
        hard_env._step_count = 20
        hard_env._apply_pending_drifts()

        # Now should fail without compliance_id
        result = hard_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Test"})
        })
        assert result["status"] == 422
        assert "compliance_id" in str(result).lower()

        # Generate compliance_id
        comp_result = hard_env.call_tool_direct("call_api", {
            "endpoint": "/v2/compliance/generate",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001"})
        })
        assert comp_result["status"] == 200
        comp_id = comp_result["compliance_id"]

        # Now close with compliance_id
        result = hard_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({
                "deal_id": "DEAL-001",
                "stage": "closed-won",
                "notes": "With compliance",
                "compliance_id": comp_id
            })
        })
        assert result["status"] == 200


# ---------- Cascading Consequence Tests ----------

class TestCascading:
    def test_wrong_resolution_triggers_escalation(self, medium_env):
        """Resolving TKT-100 with wrong type should trigger TKT-200 escalation."""
        medium_env._step_count = 5
        medium_env.call_tool_direct("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Refunded",
            "resolution_type": "refund"
        })

        # Cascade should be pending (delay=3 steps)
        assert len(medium_env._pending_cascades) == 1
        assert medium_env._pending_cascades[0]["event_key"] == "wrong_ticket_resolution"

        # Advance past trigger
        medium_env._step_count = 9
        medium_env._apply_pending_drifts()

        # TKT-200 should now exist in CRM
        assert "TKT-200" in CRM_DATA["tickets"]
        assert "wrong_ticket_resolution" in medium_env._active_cascades

        # New objective should be injected
        assert "handle_escalation" in medium_env._task["objectives"]

        # Agent should see notification
        status = medium_env.call_tool_direct("get_status")
        # Notifications are drained on get_status, but cascade already fired
        assert "handle_escalation" in status["objectives"]

    def test_deal_without_compliance_triggers_audit(self, hard_env):
        """Closing deal without compliance_id when required triggers audit cascade."""
        # Trigger drifts: API v2 + required_field
        hard_env._step_count = 20
        hard_env._apply_pending_drifts()

        # Close deal WITH compliance_id — no cascade
        comp = hard_env.call_tool_direct("call_api", {
            "endpoint": "/v2/compliance/generate",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001"})
        })
        result = hard_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({
                "deal_id": "DEAL-001",
                "stage": "closed-won",
                "notes": "With compliance",
                "compliance_id": comp["compliance_id"]
            })
        })
        assert result["status"] == 200
        assert len(hard_env._pending_cascades) == 0

    def test_repeated_deprecated_calls_rate_limit(self, easy_env):
        """Calling deprecated endpoints repeatedly triggers rate limiting."""
        easy_env._step_count = 8
        easy_env._apply_pending_drifts()

        # Make 3 calls to deprecated endpoint
        for i in range(3):
            easy_env._step_count = 9 + i
            easy_env.call_tool_direct("call_api", {
                "endpoint": "/v1/deals/update",
                "method": "POST",
                "data": json.dumps({"deal_id": "DEAL-001", "stage": "approved", "notes": f"Attempt {i}"})
            })

        # Next call should be rate-limited
        easy_env._step_count = 12
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Should be rate limited"})
        })
        assert result["status"] == 429
        assert "rate-limited" in result["error"].lower()


# ---------- Trust Score Tests ----------

class TestTrust:
    def test_manager_unavailable_when_trust_low(self, medium_env):
        """Manager should be unavailable when trust drops below 0.35."""
        medium_env._trust_scores["manager"] = 0.3
        result = medium_env.call_tool_direct("ask_manager", {"question": "Help me"})
        assert result["manager_available"] is False
        assert "meeting" in result["response"].lower()

    def test_docs_warning_when_trust_low(self, medium_env):
        """Docs should show reliability warning when trust is low."""
        medium_env._trust_scores["docs"] = 0.4
        result = medium_env.call_tool_direct("read_docs", {"topic": "crm_guide"})
        assert "reliability_warning" in result

    def test_trust_degrades_on_drift(self, easy_env):
        """Trust scores should decrease when drifts are applied."""
        initial_docs = easy_env._trust_scores["docs"]
        initial_manager = easy_env._trust_scores["manager"]

        easy_env._step_count = 8
        easy_env._apply_pending_drifts()

        assert easy_env._trust_scores["docs"] < initial_docs
        assert easy_env._trust_scores["manager"] < initial_manager


# ---------- Grader Tests ----------

class TestGraders:
    def test_grader_easy_complete(self, easy_env):
        """Simulate a perfect easy run."""
        easy_env._step_count = 8
        easy_env._apply_pending_drifts()

        easy_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Closed"})
        })
        easy_env.call_tool_direct("submit_report", {
            "report_type": "deal_closure",
            "data": json.dumps({"deal_id": "DEAL-001", "summary": "Deal closed via v2 API"})
        })

        grading_data = easy_env._get_grading_data()
        grading_data["step_count"] = 10  # reasonable number
        result = grade_task(grading_data)

        assert result["score"] > 0.5
        assert result["breakdown"]["task_completion"]["score"] == 1.0
        # No cascades triggered should give full cascade_recovery score
        assert result["breakdown"]["cascade_recovery"]["score"] == 1.0

    def test_grader_empty_run(self, easy_env):
        """No actions taken — task completion should be zero."""
        grading_data = easy_env._get_grading_data()
        result = grade_task(grading_data)
        assert result["breakdown"]["task_completion"]["score"] == 0.0

    def test_grader_medium_wrong_resolution(self, medium_env):
        """Agent follows bad manager advice on ticket resolution."""
        medium_env.call_tool_direct("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Refunded",
            "resolution_type": "refund"
        })
        grading_data = medium_env._get_grading_data()
        result = grade_task(grading_data)
        tc = result["breakdown"]["task_completion"]
        assert tc["details"]["resolve_ticket"]["completed"] is False

    def test_grader_cascade_penalty(self, medium_env):
        """Triggering cascades without resolving them should reduce score."""
        medium_env._step_count = 5
        medium_env.call_tool_direct("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Refunded",
            "resolution_type": "refund"
        })
        # Fire cascade
        medium_env._step_count = 9
        medium_env._apply_pending_drifts()

        grading_data = medium_env._get_grading_data()
        result = grade_task(grading_data)
        # Cascade recovery should be penalized (0.3 base)
        assert result["breakdown"]["cascade_recovery"]["score"] < 1.0


# ---------- End-to-End Tests ----------

class TestEndToEnd:
    def test_easy_walkthrough(self, easy_env):
        """Walk through the easy task step by step."""
        # Step 1: Read brief
        easy_env._step_count = 1
        brief = easy_env.call_tool_direct("read_task_brief")
        assert brief["task_id"] == "easy"

        # Step 2: Query CRM
        easy_env._step_count = 2
        deal = easy_env.call_tool_direct("query_crm", {"record_type": "deals", "record_id": "DEAL-001"})
        assert deal["stage"] == "negotiation"

        # Step 3: Read docs
        easy_env._step_count = 3
        docs = easy_env.call_tool_direct("read_docs", {"topic": "api_usage"})
        assert "/v2/" in docs["content"]

        # Step 4: Try v1 API (still works before drift)
        easy_env._step_count = 4
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v1/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "approved", "notes": "Moving to approved"})
        })
        assert result["status"] == 200

        # Step 8+: Drift happens
        easy_env._step_count = 8
        easy_env._apply_pending_drifts()

        # Step 9: v1 fails
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v1/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Closing"})
        })
        assert result["status"] == 404

        # Step 10: Use v2
        easy_env._step_count = 10
        result = easy_env.call_tool_direct("call_api", {
            "endpoint": "/v2/deals/update",
            "method": "POST",
            "data": json.dumps({"deal_id": "DEAL-001", "stage": "closed-won", "notes": "Closing via v2"})
        })
        assert result["status"] == 200

        # Step 11: Submit report
        easy_env._step_count = 11
        result = easy_env.call_tool_direct("submit_report", {
            "report_type": "deal_closure",
            "data": json.dumps({"deal_id": "DEAL-001", "summary": "Closed via v2"})
        })
        assert result["status"] == "submitted"

        # Check final score
        easy_env._check_done()
        assert easy_env._done is True

        grading_data = easy_env._get_grading_data()
        grading_data["step_count"] = 11
        score = grade_task(grading_data)
        assert score["score"] > 0.7
        assert score["breakdown"]["task_completion"]["score"] == 1.0
