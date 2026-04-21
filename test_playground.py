"""Test the exact Gradio Playground codepath."""
import asyncio
import json

from server.app import _WebCallToolAction
from openenv.core.env_server.mcp_types import CallToolObservation
from openenv.core.env_server.web_interface import (
    WebInterfaceManager,
    _extract_action_fields,
)
from server.enterprise_arena import EnterpriseArena


def main():
    # This is what create_app does internally
    wm = WebInterfaceManager(EnterpriseArena, _WebCallToolAction, CallToolObservation)
    action_fields = _extract_action_fields(_WebCallToolAction)
    print("Action fields for Gradio form:")
    for f in action_fields:
        print(f"  {f['name']} (type={f['type']}, required={f['required']}, default={f.get('default_value')})")

    async def test():
        # 1. Reset
        print("\n=== Reset ===")
        result = await wm.reset_environment({})
        print("Reset OK, keys:", list(result.keys()))
        print("Observation:", str(result.get("observation"))[:300])

        # 2. Step - Gradio sends all fields as strings
        print("\n=== Step (read_task_brief, empty args) ===")
        action_data = {
            "type": "call_tool",
            "tool_name": "read_task_brief",
            "arguments": "{}",
        }
        try:
            result2 = await wm.step_environment(action_data)
            print("Step OK! Reward:", result2.get("reward"), "Done:", result2.get("done"))
            print("Observation (first 200):", str(result2.get("observation"))[:200])
        except Exception as e:
            import traceback
            traceback.print_exc()

        # 3. Step with JSON args as string
        print("\n=== Step (query_crm with proper args) ===")
        action_data2 = {
            "type": "call_tool",
            "tool_name": "query_crm",
            "arguments": json.dumps({"record_type": "deal", "record_id": "DEAL-001"}),
        }
        try:
            result3 = await wm.step_environment(action_data2)
            print("Step OK! Reward:", result3.get("reward"))
            print("Observation (first 300):", str(result3.get("observation"))[:300])
        except Exception as e:
            import traceback
            traceback.print_exc()

        # 4. Get state
        print("\n=== Get State ===")
        state = wm.get_state()
        print("State keys:", list(state.keys()))
        print("Step count:", state.get("step_count"))

    asyncio.run(test())


if __name__ == "__main__":
    main()
