"""
FastAPI application for the Enterprise Arena environment.

Uses create_app for WebSocket/Playground, plus custom HTTP routes
with a singleton environment for stateful multi-step episodes.
"""

import inspect
import json
import logging
from typing import Any, Dict, Optional

from fastapi import Body
from pydantic import BaseModel, ConfigDict

try:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from .enterprise_arena import EnterpriseArena
except ImportError:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from server.enterprise_arena import EnterpriseArena

logger = logging.getLogger(__name__)

# Create base app (WebSocket, Playground, /health, /web)
app = create_app(
    EnterpriseArena,
    CallToolAction,
    CallToolObservation,
    env_name="enterprise_arena",
)

# Remove framework's HTTP routes — use our singleton routes instead
_override_paths = {"/step", "/reset", "/state"}
app.routes[:] = [
    r for r in app.routes
    if not (hasattr(r, "path") and r.path in _override_paths)
]

# --- Singleton environment for stateful HTTP ---
_env: Optional[EnterpriseArena] = None


def _get_env() -> EnterpriseArena:
    global _env
    if _env is None:
        _env = EnterpriseArena()
    return _env


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    seed: Optional[int] = None
    episode_id: Optional[str] = None
    task_id: str = "easy"


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: Dict[str, Any]


@app.post("/reset")
async def custom_reset(request: ResetRequest = Body(default_factory=ResetRequest)):
    env = _get_env()
    kwargs = request.model_dump(exclude_unset=True)
    sig = inspect.signature(env.reset)
    valid = {k: v for k, v in kwargs.items() if k in sig.parameters}
    obs = env.reset(**valid)
    obs_dict = {}
    if obs.metadata:
        obs_dict = obs.metadata if isinstance(obs.metadata, dict) else {"metadata": obs.metadata}
    return {"observation": obs_dict, "reward": obs.reward, "done": obs.done}


@app.post("/step")
async def custom_step(request: StepRequest):
    env = _get_env()
    action_data = request.action
    tool_name = action_data.get("tool_name") or action_data.get("name")
    arguments = action_data.get("arguments") or {}

    if not tool_name:
        return {"observation": {"error": "Missing 'tool_name' in action"}, "reward": 0.0, "done": False}

    # Track step count and apply drifts
    env._step_count += 1
    env._state.step_count = env._step_count
    env._apply_pending_drifts()

    if env._step_count >= env._max_steps:
        env._done = True

    result = env.call_tool_direct(tool_name, arguments)
    env._check_done()
    reward = env._compute_reward()
    done = env._done

    obs_dict = {"tool_name": tool_name, "result": result}

    if done and env._task:
        try:
            from .graders import GRADERS
        except ImportError:
            from server.graders import GRADERS
        grading_data = env._get_grading_data()
        grader = GRADERS.get(env._task["task_id"])
        if grader:
            final = grader(grading_data)
            obs_dict["final_score"] = final.get("score", 0.0)
            obs_dict["final_breakdown"] = final.get("breakdown", {})
            obs_dict["episode_complete"] = True

    return {"observation": obs_dict, "reward": reward, "done": done}


@app.get("/state")
async def custom_state():
    env = _get_env()
    s = env.state
    return {"episode_id": s.episode_id, "step_count": s.step_count}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
