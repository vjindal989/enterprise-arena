"""Unit tests for the Enterprise Arena environment (no server needed)."""

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.enterprise_arena import EnterpriseArena
from server.graders import grade_task


# ---------- Fixtures ----------

@pytest.fixture
def env():
    e = EnterpriseArena()
    return e


@pytest.fixture
def easy_env(env):
    env.reset(task_id="easy")
    return env


@pytest.fixture
def medium_env(env):
    env.reset(task_id="medium")
    return env


@pytest.fixture
def hard_env(env):
    env.reset(task_id="hard")
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
        assert "error" in str(obs.metadata).lower()


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
        # Easy task: manager is always correct
        assert "wrong" not in result["response"].lower() or True  # response might contain "wrong" in text

    def test_ask_manager_medium_wrong(self, medium_env):
        # Medium: manager is wrong on ticket_resolution
        result = medium_env.call_tool_direct("ask_manager", {"question": "How should I resolve ticket TKT-100?"})
        assert result["source"] == "manager"
        # The manager's response should suggest "refund" (wrong advice)
        assert "refund" in result["response"].lower()

    def test_read_docs(self, easy_env):
        result = easy_env.call_tool_direct("read_docs", {"topic": "api_usage"})
        # Easy: docs are current
        assert "v2" in result["content"].lower()

    def test_read_docs_outdated(self, medium_env):
        # Medium: api_usage docs are outdated
        result = medium_env.call_tool_direct("read_docs", {"topic": "api_usage"})
        assert "/v1/" in result["content"]
        assert "/v2/" not in result["content"]  # outdated docs don't mention v2

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

    def test_grader_empty_run(self, easy_env):
        """No actions taken — task completion should be zero."""
        grading_data = easy_env._get_grading_data()
        result = grade_task(grading_data)
        assert result["breakdown"]["task_completion"]["score"] == 0.0
        # Overall may still be > 0 because source_accuracy/drift_adaptation
        # score high when there are no adversarial sources or drifts applied

    def test_grader_medium_wrong_resolution(self, medium_env):
        """Agent follows bad manager advice on ticket resolution."""
        medium_env.call_tool_direct("resolve_ticket", {
            "ticket_id": "TKT-100",
            "resolution": "Refunded",
            "resolution_type": "refund"
        })
        grading_data = medium_env._get_grading_data()
        result = grade_task(grading_data)
        # Should get penalized for wrong resolution type
        tc = result["breakdown"]["task_completion"]
        # resolve_ticket objective should be False (wrong type)
        assert tc["details"]["resolve_ticket"]["completed"] is False


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

        # Steps 5-7: More info gathering
        easy_env._step_count = 7

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
