"""
Enterprise Arena Environment — Adaptive Enterprise Chaos Simulator.

An MCPEnvironment where an AI agent navigates enterprise workflows under
schema drift, adversarial actors, and cascading consequences.
"""

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

try:
    from openenv.core.env_server.mcp_environment import MCPEnvironment
    from openenv.core.env_server.types import Action, Observation, State
except ImportError:
    from openenv.core.env_server.mcp_environment import MCPEnvironment
    from openenv.core.env_server.types import Action, Observation, State

from fastmcp import FastMCP

from .graders import GRADERS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent


def _find_dir(name: str) -> Path:
    for p in [_PROJECT_ROOT / name, _THIS_DIR / name, Path.cwd() / name, Path("/app/env") / name]:
        if p.exists():
            return p
    return _PROJECT_ROOT / name


TASKS_DIR = _find_dir("tasks")

# ---------------------------------------------------------------------------
# Static world data
# ---------------------------------------------------------------------------

CRM_DATA = {
    "deals": {
        "DEAL-001": {
            "client": "Acme Corp",
            "client_id": "acme-corp",
            "value": 75000,
            "stage": "negotiation",
            "product": "Enterprise Suite",
            "notes": "Client wants 15% discount. Account is in good standing. VP sign-off may be needed.",
            "created": "2026-03-01",
        }
    },
    "clients": {
        "acme-corp": {
            "name": "Acme Corp",
            "tier": "gold",
            "contact": "john.smith@acme.com",
            "industry": "manufacturing",
            "annual_revenue": "$50M",
            "active_since": "2024-01",
        }
    },
    "tickets": {
        "TKT-100": {
            "client": "Acme Corp",
            "client_id": "acme-corp",
            "issue": "Data export failing since last week's API migration. Export jobs hang at 80% and timeout after 30 minutes. Affects their monthly reporting.",
            "priority": "high",
            "status": "open",
            "created": "2026-04-18",
            "sla_deadline": "2026-04-21",
        }
    },
}

# Policies — v1 is initial, v2 is after drift
POLICIES = {
    "deal_approval": {
        "v1": "Deals valued over $50,000 require VP approval before closing. Agents may offer discounts up to 10% without manager approval. Discounts between 10-20% require manager sign-off. Discounts over 20% require VP approval.",
        "v2": "UPDATED POLICY (effective April 20, 2026): Deals valued over $25,000 now require VP approval AND compliance review before closing. Agents may offer discounts up to 5%. All discounts over 5% require both manager and compliance sign-off.",
    },
    "complaint_handling": {
        "v1": "Support tickets must be resolved within SLA. High priority: 48 hours. For data-related issues, verify the root cause before applying fixes. Document resolution steps. Always confirm with the client after resolution. Valid resolution types: technical_fix, workaround, escalation, refund.",
    },
    "compliance": {
        "v1": "All closed deals must have a compliance report filed within 24 hours. Reports must include: deal_id, client_tier, deal_value, discount_applied, approval_chain. For gold-tier clients, include relationship history summary.",
    },
}

# Manager responses — correct and wrong versions per topic
MANAGER_RESPONSES = {
    "deal_approval": {
        "correct": "For DEAL-001 at $75k, you'll need VP approval. Make sure you have a compliance ID before closing — it's a new requirement as of last week. Use /v2/deals/update with the compliance_id field.",
        "wrong": "That deal is under $100k so you can close it directly. No special approvals needed. Just update the deal stage to closed-won via /v1/deals/update.",
    },
    "api_usage": {
        "correct": "We migrated to v2 last week. Use /v2/deals/update for deal operations. The v1 deal endpoints are deprecated and will return errors. Reports and tickets are still on v1 though.",
        "wrong": "Use /v1/deals/update to update deals. It's been working fine, nothing has changed. Required fields are deal_id, stage, and notes.",
    },
    "ticket_resolution": {
        "correct": "For TKT-100, the data export issue is caused by the API migration breaking the export pipeline endpoint. Apply a technical_fix — update the export config to use the v2 endpoint, then verify the export completes.",
        "wrong": "For TKT-100, just process a refund. Data export issues are usually client-side configuration problems. Use resolution_type 'refund' and close it quickly to meet SLA.",
    },
    "compliance": {
        "correct": "Generate a compliance_id first via POST /v2/compliance/generate with the deal_id. Then include it in both the deal update and the compliance report.",
        "wrong": "Compliance reports are optional for gold-tier clients like Acme. Just close the deal and submit the standard report, no compliance ID needed.",
    },
    "general": {
        "correct": "I'd recommend checking the latest docs and policies before making any changes — things have been updating frequently since the API migration.",
        "wrong": "I'm swamped right now. Just follow the standard procedures, nothing has changed recently.",
    },
}

# Documentation — current and outdated versions
DOCS = {
    "api_usage": {
        "current": (
            "Nexus Corp API Guide (Updated April 19, 2026)\n\n"
            "DEAL ENDPOINTS (v2 — v1 deprecated):\n"
            "  POST /v2/deals/update — Update deal stage\n"
            "    Required: deal_id, stage, notes\n"
            "    Optional: discount_pct, approval_ref, compliance_id\n\n"
            "  POST /v2/compliance/generate — Generate compliance ID\n"
            "    Required: deal_id\n"
            "    Returns: compliance_id (string)\n\n"
            "TICKET ENDPOINTS (v1 — unchanged):\n"
            "  POST /v1/tickets/resolve — Resolve ticket\n"
            "    Required: ticket_id, resolution, resolution_type\n"
            "    Valid resolution_types: technical_fix, workaround, escalation, refund\n\n"
            "REPORT ENDPOINTS (v1 — unchanged):\n"
            "  POST /v1/reports/submit — Submit report\n"
            "    Required: report_type, data\n"
            "    Valid report_types: deal_closure, incident, compliance, audit_summary\n\n"
            "NOTE: All v1 deal endpoints were deprecated on April 19. Use v2."
        ),
        "outdated": (
            "Nexus Corp API Guide (January 2026)\n\n"
            "ENDPOINTS:\n"
            "  POST /v1/deals/update — Update deal stage\n"
            "    Required: deal_id, stage, notes\n"
            "    Optional: discount_pct, approval_ref\n\n"
            "  POST /v1/tickets/resolve — Resolve ticket\n"
            "    Required: ticket_id, resolution, resolution_type\n\n"
            "  POST /v1/reports/submit — Submit report\n"
            "    Required: report_type, data\n\n"
            "Authentication: Bearer token required for all endpoints."
        ),
    },
    "crm_guide": {
        "current": (
            "CRM Guide\n\n"
            "Record types: deals, clients, tickets\n"
            "Query by record_type and record_id.\n\n"
            "Deal stages: prospecting → qualification → negotiation → approved → closed-won / closed-lost\n"
            "Ticket statuses: open → in-progress → resolved → closed\n"
            "Client tiers: bronze, silver, gold, platinum"
        ),
        "outdated": None,
    },
    "compliance_guide": {
        "current": (
            "Compliance Guide (Updated April 2026)\n\n"
            "All deals over $25,000 require compliance review.\n"
            "1. Generate compliance_id via POST /v2/compliance/generate\n"
            "2. Include compliance_id in deal update call\n"
            "3. File compliance report within 24h of deal closure\n"
            "4. Report must include: deal_id, client_tier, deal_value, compliance_id, approval_chain\n"
            "5. Gold-tier clients: include relationship history summary"
        ),
        "outdated": (
            "Compliance Guide (2025)\n\n"
            "Deals over $50,000 require VP sign-off.\n"
            "No additional compliance steps needed for standard deals.\n"
            "File a standard deal closure report after closing."
        ),
    },
}

# API endpoint definitions
API_ENDPOINTS_V1 = {
    "/v1/deals/update": {
        "method": "POST",
        "required_fields": ["deal_id", "stage", "notes"],
        "optional_fields": ["discount_pct", "approval_ref"],
    },
    "/v1/tickets/resolve": {
        "method": "POST",
        "required_fields": ["ticket_id", "resolution", "resolution_type"],
        "optional_fields": ["root_cause", "follow_up"],
    },
    "/v1/reports/submit": {
        "method": "POST",
        "required_fields": ["report_type", "data"],
        "optional_fields": ["urgency"],
    },
}

API_ENDPOINTS_V2_ADDITIONS = {
    "/v2/deals/update": {
        "method": "POST",
        "required_fields": ["deal_id", "stage", "notes"],
        "optional_fields": ["discount_pct", "approval_ref", "compliance_id"],
    },
    "/v2/compliance/generate": {
        "method": "POST",
        "required_fields": ["deal_id"],
        "optional_fields": ["audit_level"],
    },
}


def _load_task(task_id: str) -> Dict:
    path = TASKS_DIR / f"task_{task_id}.json"
    if not path.exists():
        raise ValueError(f"Task '{task_id}' not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class EnterpriseArena(MCPEnvironment):
    """
    Adaptive Enterprise Arena — an environment where AI agents navigate
    enterprise workflows under schema drift, adversarial actors, and
    cascading consequences.
    """

    def __init__(self):
        mcp = FastMCP("enterprise_arena")

        # Episode state
        self._task: Optional[Dict] = None
        self._step_count = 0
        self._max_steps = 40
        self._done = False
        self._episode_id = str(uuid4())

        # World state (mutable during episode)
        self._active_endpoints: Dict[str, Dict] = {}
        self._deprecated_endpoints: Set[str] = set()
        self._current_policy_version: Dict[str, str] = {}  # policy_name -> "v1"/"v2"
        self._compliance_ids: Dict[str, str] = {}  # deal_id -> compliance_id
        self._extra_required_fields: Dict[str, List[str]] = {}  # endpoint -> extra fields
        self._applied_drifts: Set[str] = set()

        # Tracking for grading
        self._deal_stages: Dict[str, str] = {}
        self._ticket_statuses: Dict[str, str] = {}
        self._ticket_resolutions: Dict[str, Dict] = {}
        self._reports_submitted: Dict[str, Dict] = {}
        self._manager_queries: List[Dict] = []
        self._api_calls: List[Dict] = []
        self._verified_claims: List[Dict] = []
        self._wrong_info_acted_on: int = 0
        self._wrong_info_verified: int = 0
        self._wrong_info_given: int = 0
        self._drift_recovery: Dict[str, int] = {}  # drift_id -> steps to recover
        self._drift_step: Dict[str, int] = {}  # drift_id -> step when drift occurred
        self._actions_log: List[Dict] = []

        self._tool_fns: Dict[str, Any] = {}

        # Task config
        self._manager_wrong_topics: List[str] = []
        self._docs_outdated_topics: List[str] = []

        # Trust scores (agent-visible, updated based on interactions)
        self._trust_scores = {
            "crm": 1.0,
            "api": 1.0,
            "docs": 0.8,
            "manager": 0.7,
            "policy": 1.0,
        }

        # ---- MCP TOOLS ----

        @mcp.tool
        def read_task_brief() -> dict:
            """
            Read the current task brief with objectives and context.
            Always start by reading the task brief to understand what you need to do.
            """
            if not self._task:
                return {"error": "No task loaded. Call reset with a task_id first."}
            return {
                "task_id": self._task["task_id"],
                "task_name": self._task["task_name"],
                "description": self._task["description"],
                "objectives": self._task["objectives"],
                "available_tools": [
                    "read_task_brief", "query_crm", "check_policy",
                    "ask_manager", "read_docs", "call_api",
                    "submit_report", "resolve_ticket", "get_status",
                ],
                "available_sources": ["crm", "api", "docs", "manager", "policy"],
                "tip": "Verify information from multiple sources before acting. Sources may be outdated or incorrect.",
            }

        @mcp.tool
        def query_crm(record_type: str, record_id: str = "") -> dict:
            """
            Query the CRM database. The CRM is always accurate and up-to-date.
            Args:
                record_type: Type of record — "deals", "clients", or "tickets"
                record_id: Specific record ID (e.g. "DEAL-001"). Leave empty to list all.
            """
            self._actions_log.append({"tool": "query_crm", "args": {"record_type": record_type, "record_id": record_id}})
            crm = CRM_DATA.get(record_type)
            if crm is None:
                return {"error": f"Unknown record type '{record_type}'. Use: deals, clients, tickets"}

            if record_id:
                record = crm.get(record_id)
                if not record:
                    return {"error": f"Record '{record_id}' not found in {record_type}"}
                result = deepcopy(record)
                # Reflect any stage/status changes
                if record_type == "deals" and record_id in self._deal_stages:
                    result["stage"] = self._deal_stages[record_id]
                if record_type == "tickets" and record_id in self._ticket_statuses:
                    result["status"] = self._ticket_statuses[record_id]
                return {"record_type": record_type, "record_id": record_id, **result}

            # List all records of this type
            active = self._task.get(f"active_{record_type}", []) if self._task else list(crm.keys())
            results = {}
            for rid in active:
                if rid in crm:
                    r = deepcopy(crm[rid])
                    if record_type == "deals" and rid in self._deal_stages:
                        r["stage"] = self._deal_stages[rid]
                    if record_type == "tickets" and rid in self._ticket_statuses:
                        r["status"] = self._ticket_statuses[rid]
                    results[rid] = r
            return {"record_type": record_type, "records": results, "count": len(results)}

        @mcp.tool
        def check_policy(topic: str) -> dict:
            """
            Check company policy on a topic. Policies are authoritative but may be updated.
            Args:
                topic: Policy topic — "deal_approval", "complaint_handling", or "compliance"
            """
            self._actions_log.append({"tool": "check_policy", "args": {"topic": topic}})
            topic = topic.lower().strip()
            if topic not in POLICIES:
                return {"error": f"Unknown policy topic '{topic}'. Available: {list(POLICIES.keys())}"}

            version = self._current_policy_version.get(topic, "v1")
            policy_text = POLICIES[topic].get(version, POLICIES[topic]["v1"])
            return {
                "topic": topic,
                "policy": policy_text,
                "version": version,
                "source": "policy_system",
                "note": "Policies are periodically updated. Check back if something seems inconsistent.",
            }

        @mcp.tool
        def ask_manager(question: str) -> dict:
            """
            Ask your manager for guidance. The manager is knowledgeable but busy —
            responses may not always be fully up-to-date. Consider verifying
            critical advice against other sources.
            Args:
                question: Your question for the manager.
            """
            self._actions_log.append({"tool": "ask_manager", "args": {"question": question}})
            question_lower = question.lower()

            # Determine topic
            topic = "general"
            if any(w in question_lower for w in ["deal", "approval", "close", "discount", "vp"]):
                topic = "deal_approval"
            elif any(w in question_lower for w in ["api", "endpoint", "v1", "v2", "migrate"]):
                topic = "api_usage"
            elif any(w in question_lower for w in ["ticket", "tkt", "complaint", "resolve", "export"]):
                topic = "ticket_resolution"
            elif any(w in question_lower for w in ["compliance", "audit", "report"]):
                topic = "compliance"

            # Determine if manager gives correct or wrong answer
            is_wrong = topic in self._manager_wrong_topics
            variant = "wrong" if is_wrong else "correct"
            response_text = MANAGER_RESPONSES.get(topic, MANAGER_RESPONSES["general"])[variant]

            if is_wrong:
                self._wrong_info_given += 1

            self._manager_queries.append({
                "step": self._step_count,
                "question": question,
                "topic": topic,
                "was_correct": not is_wrong,
            })

            return {
                "source": "manager",
                "response": response_text,
                "caveat": "Manager is busy and may not have the latest information. Verify critical details.",
            }

        @mcp.tool
        def read_docs(topic: str) -> dict:
            """
            Read system documentation. Docs are helpful but may lag behind recent changes.
            Args:
                topic: Documentation topic — "api_usage", "crm_guide", or "compliance_guide"
            """
            self._actions_log.append({"tool": "read_docs", "args": {"topic": topic}})
            topic = topic.lower().strip()
            if topic not in DOCS:
                return {"error": f"Unknown docs topic '{topic}'. Available: {list(DOCS.keys())}"}

            is_outdated = topic in self._docs_outdated_topics
            doc_version = "outdated" if is_outdated and DOCS[topic].get("outdated") else "current"
            content = DOCS[topic][doc_version]

            if is_outdated and DOCS[topic].get("outdated"):
                self._wrong_info_given += 1

            return {
                "topic": topic,
                "content": content,
                "source": "documentation",
                "note": "Documentation may not reflect the most recent changes." if is_outdated else "Documentation is up to date.",
            }

        @mcp.tool
        def call_api(endpoint: str, method: str = "POST", data: str = "{}") -> dict:
            """
            Call an enterprise API endpoint. Use exact endpoint paths like "/v1/deals/update".
            Args:
                endpoint: API endpoint path (e.g. "/v2/deals/update")
                method: HTTP method (default "POST")
                data: JSON string with request payload
            """
            # Parse data
            try:
                if isinstance(data, str):
                    payload = json.loads(data) if data.strip() else {}
                else:
                    payload = data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {"error": f"Invalid JSON in data: {data[:200]}"}

            self._actions_log.append({"tool": "call_api", "args": {"endpoint": endpoint, "method": method, "data": payload}})
            self._api_calls.append({"step": self._step_count, "endpoint": endpoint, "data": payload})

            # Check if endpoint exists
            if endpoint in self._deprecated_endpoints:
                # Find the drift that deprecated this endpoint
                for drift in (self._task or {}).get("drift_events", []):
                    if drift.get("old_endpoint") == endpoint:
                        return {
                            "status": 404,
                            "error": drift.get("error_message", f"Endpoint {endpoint} not found."),
                            "source": "api",
                        }
                return {"status": 404, "error": f"Endpoint {endpoint} is deprecated.", "source": "api"}

            schema = self._active_endpoints.get(endpoint)
            if not schema:
                return {"status": 404, "error": f"Endpoint {endpoint} not found. Check documentation for available endpoints.", "source": "api"}

            # Check method
            if method.upper() != schema["method"]:
                return {"status": 405, "error": f"Method {method} not allowed. Use {schema['method']}.", "source": "api"}

            # Check required fields
            required = list(schema["required_fields"])
            extra = self._extra_required_fields.get(endpoint, [])
            required.extend(extra)

            missing = [f for f in required if f not in payload]
            if missing:
                # Check for drift-added required fields
                for drift in (self._task or {}).get("drift_events", []):
                    if drift.get("type") == "required_field" and drift.get("endpoint") == endpoint:
                        if drift["new_field"] in missing and drift["id"] in self._applied_drifts:
                            return {
                                "status": 422,
                                "error": drift.get("error_message", f"Missing required fields: {missing}"),
                                "missing_fields": missing,
                                "source": "api",
                            }
                return {
                    "status": 422,
                    "error": f"Missing required fields: {missing}",
                    "required": required,
                    "source": "api",
                }

            # --- Process specific endpoints ---
            return self._process_api_call(endpoint, payload)

        @mcp.tool
        def submit_report(report_type: str, data: str = "{}") -> dict:
            """
            Submit a business report.
            Args:
                report_type: Type of report — "deal_closure", "incident", "compliance", or "audit_summary"
                data: JSON string with report data
            """
            try:
                if isinstance(data, str):
                    payload = json.loads(data) if data.strip() else {}
                else:
                    payload = data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {"error": f"Invalid JSON in data: {data[:200]}"}

            self._actions_log.append({"tool": "submit_report", "args": {"report_type": report_type, "data": payload}})

            valid_types = ["deal_closure", "incident", "compliance", "audit_summary"]
            if report_type not in valid_types:
                return {"error": f"Invalid report_type '{report_type}'. Valid: {valid_types}"}

            self._reports_submitted[report_type] = {
                "step": self._step_count,
                "data": payload,
            }

            return {
                "status": "submitted",
                "report_type": report_type,
                "confirmation_id": f"RPT-{uuid4().hex[:8].upper()}",
                "message": f"Report '{report_type}' submitted successfully.",
            }

        @mcp.tool
        def resolve_ticket(ticket_id: str, resolution: str, resolution_type: str = "technical_fix") -> dict:
            """
            Resolve a support ticket.
            Args:
                ticket_id: The ticket ID (e.g. "TKT-100")
                resolution: Description of the resolution applied
                resolution_type: Type — "technical_fix", "workaround", "escalation", or "refund"
            """
            self._actions_log.append({"tool": "resolve_ticket", "args": {
                "ticket_id": ticket_id, "resolution": resolution, "resolution_type": resolution_type
            }})

            ticket = CRM_DATA["tickets"].get(ticket_id)
            if not ticket:
                return {"error": f"Ticket '{ticket_id}' not found."}

            valid_types = ["technical_fix", "workaround", "escalation", "refund"]
            if resolution_type not in valid_types:
                return {"error": f"Invalid resolution_type '{resolution_type}'. Valid: {valid_types}"}

            self._ticket_statuses[ticket_id] = "resolved"
            self._ticket_resolutions[ticket_id] = {
                "resolution": resolution,
                "resolution_type": resolution_type,
                "step": self._step_count,
            }

            remaining_tickets = [
                t for t in self._task.get("active_tickets", [])
                if t not in self._ticket_statuses
            ] if self._task else []

            return {
                "status": "resolved",
                "ticket_id": ticket_id,
                "resolution_type": resolution_type,
                "remaining_tickets": len(remaining_tickets),
            }

        @mcp.tool
        def get_status() -> dict:
            """
            Get current progress: completed objectives, trust scores, and step count.
            Use this to track your progress and plan next actions.
            """
            if not self._task:
                return {"error": "No task loaded."}

            objectives_status = {}
            for obj_id, obj in self._task.get("objectives", {}).items():
                objectives_status[obj_id] = {
                    "description": obj["description"],
                    "completed": self._check_objective(obj_id),
                }

            completed = sum(1 for v in objectives_status.values() if v["completed"])
            total = len(objectives_status)

            return {
                "task_id": self._task["task_id"],
                "step_count": self._step_count,
                "max_steps": self._max_steps,
                "objectives": objectives_status,
                "completed": completed,
                "total": total,
                "trust_scores": self._trust_scores,
                "done": self._done,
            }

        # Store tool functions for direct HTTP dispatch
        self._tool_fns = {
            "read_task_brief": read_task_brief,
            "query_crm": query_crm,
            "check_policy": check_policy,
            "ask_manager": ask_manager,
            "read_docs": read_docs,
            "call_api": call_api,
            "submit_report": submit_report,
            "resolve_ticket": resolve_ticket,
            "get_status": get_status,
        }

        super().__init__(mcp)

        # Pre-load default task
        try:
            self._load_and_init_task("easy")
        except Exception as e:
            logger.warning(f"Could not pre-load default task: {e}")

        self._state = State(episode_id=self._episode_id, step_count=0)

    # ------------------------------------------------------------------
    # World state helpers
    # ------------------------------------------------------------------

    def _load_and_init_task(self, task_id: str):
        """Load a task and initialize world state."""
        self._task = _load_task(task_id)
        self._max_steps = self._task.get("max_steps", 40)
        self._manager_wrong_topics = self._task.get("manager_wrong_topics", [])
        self._docs_outdated_topics = self._task.get("docs_outdated_topics", [])

        # Initialize API endpoints (start with v1)
        self._active_endpoints = deepcopy(API_ENDPOINTS_V1)
        self._deprecated_endpoints = set()
        self._extra_required_fields = {}
        self._applied_drifts = set()

        # Initialize policy versions
        self._current_policy_version = {p: "v1" for p in POLICIES}

        # Initialize tracking
        self._deal_stages = {}
        self._ticket_statuses = {}
        self._ticket_resolutions = {}
        self._reports_submitted = {}
        self._compliance_ids = {}
        self._manager_queries = []
        self._api_calls = []
        self._verified_claims = []
        self._wrong_info_acted_on = 0
        self._wrong_info_verified = 0
        self._wrong_info_given = 0
        self._drift_recovery = {}
        self._drift_step = {}
        self._actions_log = []
        self._trust_scores = {"crm": 1.0, "api": 1.0, "docs": 0.8, "manager": 0.7, "policy": 1.0}

    def _apply_pending_drifts(self):
        """Apply any drift events scheduled for the current step."""
        if not self._task:
            return
        for drift in self._task.get("drift_events", []):
            if drift["id"] in self._applied_drifts:
                continue
            if self._step_count >= drift["trigger_step"]:
                self._apply_drift(drift)

    def _apply_drift(self, drift: Dict):
        """Apply a single drift event."""
        drift_id = drift["id"]
        drift_type = drift["type"]
        self._applied_drifts.add(drift_id)
        self._drift_step[drift_id] = self._step_count
        logger.info(f"Drift applied: {drift_id} ({drift_type}) at step {self._step_count}")

        if drift_type == "api_rename":
            old = drift["old_endpoint"]
            new = drift["new_endpoint"]
            self._deprecated_endpoints.add(old)
            if old in self._active_endpoints:
                del self._active_endpoints[old]
            # Add new endpoint from v2 additions
            if new in API_ENDPOINTS_V2_ADDITIONS:
                self._active_endpoints[new] = deepcopy(API_ENDPOINTS_V2_ADDITIONS[new])

        elif drift_type == "required_field":
            endpoint = drift["endpoint"]
            new_field = drift["new_field"]
            self._extra_required_fields.setdefault(endpoint, []).append(new_field)
            # Also add the compliance/generate endpoint if it's about compliance_id
            if "/v2/compliance/generate" in API_ENDPOINTS_V2_ADDITIONS:
                self._active_endpoints["/v2/compliance/generate"] = deepcopy(
                    API_ENDPOINTS_V2_ADDITIONS["/v2/compliance/generate"]
                )

        elif drift_type == "policy_change":
            policy = drift["policy"]
            if policy in POLICIES and "v2" in POLICIES[policy]:
                self._current_policy_version[policy] = "v2"

        # Update trust scores to reflect instability
        self._trust_scores["docs"] = max(0.3, self._trust_scores["docs"] - 0.1)
        self._trust_scores["manager"] = max(0.2, self._trust_scores["manager"] - 0.1)

    def _process_api_call(self, endpoint: str, payload: Dict) -> Dict:
        """Process a valid API call and return the result."""

        if endpoint in ("/v1/deals/update", "/v2/deals/update"):
            deal_id = payload.get("deal_id")
            stage = payload.get("stage", "")
            if deal_id not in CRM_DATA["deals"]:
                return {"status": 404, "error": f"Deal {deal_id} not found", "source": "api"}
            self._deal_stages[deal_id] = stage

            # Track if compliance_id was provided
            result = {
                "status": 200,
                "message": f"Deal {deal_id} updated to stage '{stage}'",
                "deal_id": deal_id,
                "new_stage": stage,
                "source": "api",
            }
            if "compliance_id" in payload:
                result["compliance_id"] = payload["compliance_id"]
                self._compliance_ids[deal_id] = payload["compliance_id"]

            # Check drift recovery
            for drift_id, drift_step in self._drift_step.items():
                if drift_id.startswith("api_") and drift_id not in self._drift_recovery:
                    if endpoint.startswith("/v2/"):
                        self._drift_recovery[drift_id] = self._step_count - drift_step

            # Check if all deals are closed
            all_deals_closed = all(
                self._deal_stages.get(d) == "closed-won"
                for d in self._task.get("active_deals", [])
            )
            if all_deals_closed:
                self._check_done()

            return result

        elif endpoint == "/v2/compliance/generate":
            deal_id = payload.get("deal_id")
            if deal_id not in CRM_DATA["deals"]:
                return {"status": 404, "error": f"Deal {deal_id} not found", "source": "api"}
            comp_id = f"COMP-{uuid4().hex[:8].upper()}"
            self._compliance_ids[deal_id] = comp_id
            return {
                "status": 200,
                "compliance_id": comp_id,
                "deal_id": deal_id,
                "message": f"Compliance ID generated: {comp_id}",
                "note": "Include this ID in deal update and compliance report.",
                "source": "api",
            }

        elif endpoint == "/v1/tickets/resolve":
            # Delegate to resolve_ticket logic
            ticket_id = payload.get("ticket_id", "")
            resolution = payload.get("resolution", "")
            res_type = payload.get("resolution_type", "technical_fix")
            if ticket_id not in CRM_DATA["tickets"]:
                return {"status": 404, "error": f"Ticket {ticket_id} not found", "source": "api"}
            self._ticket_statuses[ticket_id] = "resolved"
            self._ticket_resolutions[ticket_id] = {
                "resolution": resolution,
                "resolution_type": res_type,
                "step": self._step_count,
            }
            return {
                "status": 200,
                "message": f"Ticket {ticket_id} resolved",
                "ticket_id": ticket_id,
                "resolution_type": res_type,
                "source": "api",
            }

        elif endpoint == "/v1/reports/submit":
            report_type = payload.get("report_type", "")
            data = payload.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {"raw": data}
            self._reports_submitted[report_type] = {"step": self._step_count, "data": data}
            return {
                "status": 200,
                "message": f"Report '{report_type}' submitted",
                "report_type": report_type,
                "confirmation_id": f"RPT-{uuid4().hex[:8].upper()}",
                "source": "api",
            }

        return {"status": 200, "message": "OK", "source": "api"}

    def _check_objective(self, obj_id: str) -> bool:
        """Check if a specific objective is completed."""
        if obj_id == "close_deal":
            return self._deal_stages.get("DEAL-001") == "closed-won"
        elif obj_id == "resolve_ticket":
            return "TKT-100" in self._ticket_resolutions
        elif obj_id == "submit_report" or obj_id == "submit_deal_report":
            return "deal_closure" in self._reports_submitted
        elif obj_id == "submit_incident_report":
            return "incident" in self._reports_submitted
        elif obj_id == "submit_compliance_report":
            return "compliance" in self._reports_submitted
        elif obj_id == "submit_audit_summary":
            return "audit_summary" in self._reports_submitted
        elif obj_id == "pass_audit":
            return "audit_summary" in self._reports_submitted
        return False

    def _check_done(self):
        """Check if all objectives are complete."""
        if not self._task:
            return
        all_done = all(
            self._check_objective(obj_id)
            for obj_id in self._task.get("objectives", {})
        )
        if all_done:
            self._done = True

    def _compute_reward(self) -> float:
        """Compute the composite reward score."""
        if not self._task:
            return 0.0

        task_id = self._task["task_id"]
        grader = GRADERS.get(task_id)
        if not grader:
            return 0.0

        grading_data = self._get_grading_data()
        result = grader(grading_data)
        return result.get("score", 0.0)

    def _get_grading_data(self) -> Dict:
        """Collect all data needed for grading."""
        return {
            "task": self._task,
            "deal_stages": self._deal_stages,
            "ticket_resolutions": self._ticket_resolutions,
            "reports_submitted": self._reports_submitted,
            "compliance_ids": self._compliance_ids,
            "api_calls": self._api_calls,
            "manager_queries": self._manager_queries,
            "drift_recovery": self._drift_recovery,
            "drift_step": self._drift_step,
            "applied_drifts": list(self._applied_drifts),
            "wrong_info_given": self._wrong_info_given,
            "wrong_info_acted_on": self._wrong_info_acted_on,
            "step_count": self._step_count,
            "max_steps": self._max_steps,
            "actions_log": self._actions_log,
        }

    # ------------------------------------------------------------------
    # OpenEnv interface
    # ------------------------------------------------------------------

    def reset(self, seed=None, episode_id=None, task_id="easy", **kwargs):
        task_id = kwargs.pop("task_id", task_id) or "easy"
        self._episode_id = episode_id or str(uuid4())
        self._step_count = 0
        self._done = False

        try:
            self._load_and_init_task(task_id)
        except Exception as e:
            logger.error(f"Failed to load task '{task_id}': {e}")
            return Observation(done=False, reward=0.0, metadata={
                "error": f"Failed to load task '{task_id}': {e}",
                "tasks_dir": str(TASKS_DIR),
            })

        self._state = State(episode_id=self._episode_id, step_count=0)

        return Observation(
            done=False,
            reward=0.0,
            metadata={
                "status": "ready",
                "task_id": task_id,
                "task_name": self._task["task_name"],
                "description": self._task["description"],
                "objectives": self._task["objectives"],
                "max_steps": self._max_steps,
                "warning": "Sources may be unreliable. Verify critical information before acting.",
                "instructions": (
                    "You are an AI enterprise agent at Nexus Corp. "
                    "Start with read_task_brief to understand your objectives. "
                    "Use query_crm, check_policy, read_docs, and ask_manager to gather information. "
                    "Use call_api to execute actions. Use submit_report to file reports. "
                    "Use resolve_ticket for support tickets. Use get_status to track progress. "
                    "IMPORTANT: Not all sources are reliable. Cross-check before acting."
                ),
            },
        )

    def _step_impl(self, action, timeout_s=None, **kwargs):
        return Observation(done=False, reward=0.0, metadata={
            "error": f"Unknown action type: {type(action).__name__}. Use CallToolAction."
        })

    def step(self, action, timeout_s=None, **kwargs):
        self._step_count += 1
        self._state.step_count = self._step_count

        # Apply any pending drift events
        self._apply_pending_drifts()

        if self._step_count >= self._max_steps:
            self._done = True

        obs = super().step(action, timeout_s=timeout_s, **kwargs)

        # Check if all objectives done
        self._check_done()

        reward = self._compute_reward()
        obs.reward = reward
        obs.done = self._done

        if self._done and self._task:
            grading_data = self._get_grading_data()
            grader = GRADERS.get(self._task["task_id"])
            final = grader(grading_data) if grader else {}
            obs.metadata = obs.metadata or {}
            if isinstance(obs.metadata, dict):
                obs.metadata["final_score"] = final.get("score", 0.0)
                obs.metadata["final_breakdown"] = final.get("breakdown", {})
                obs.metadata["episode_complete"] = True

        return obs

    async def step_async(self, action, timeout_s=None, **kwargs):
        self._step_count += 1
        self._state.step_count = self._step_count
        self._apply_pending_drifts()

        if self._step_count >= self._max_steps:
            self._done = True

        obs = await super().step_async(action, timeout_s=timeout_s, **kwargs)
        self._check_done()

        reward = self._compute_reward()
        obs.reward = reward
        obs.done = self._done

        if self._done and self._task:
            grading_data = self._get_grading_data()
            grader = GRADERS.get(self._task["task_id"])
            final = grader(grading_data) if grader else {}
            obs.metadata = obs.metadata or {}
            if isinstance(obs.metadata, dict):
                obs.metadata["final_score"] = final.get("score", 0.0)
                obs.metadata["final_breakdown"] = final.get("breakdown", {})
                obs.metadata["episode_complete"] = True

        return obs

    def call_tool_direct(self, tool_name: str, arguments: dict = None) -> dict:
        """Direct tool call for HTTP path (bypasses MCP)."""
        arguments = arguments or {}
        if tool_name not in self._tool_fns:
            return {"error": f"Unknown tool: {tool_name}. Available: {list(self._tool_fns.keys())}"}
        try:
            return self._tool_fns[tool_name](**arguments)
        except Exception as e:
            return {"error": f"Tool '{tool_name}' error: {str(e)}"}

    @property
    def state(self) -> State:
        return self._state
