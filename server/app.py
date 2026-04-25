"""
FastAPI application for the Enterprise Arena environment.

Uses create_app for WebSocket/Playground, plus custom HTTP routes
with a singleton environment for stateful multi-step episodes.
"""

import inspect
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, field_validator

try:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from .enterprise_arena import EnterpriseArena
except ImportError:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from server.enterprise_arena import EnterpriseArena

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gradio sends form values as strings.  The framework deserialiser does NOT
# convert `arguments` from str → dict, so CallToolAction.model_validate()
# fails with "Input should be a valid dictionary".  Fix: a thin subclass
# whose pre-validator parses the string.  Because this class is NOT in the
# framework's _MCP_ACTION_TYPES dict, deserialize_action_with_preprocessing
# falls through to general processing and calls our model_validate().
# ---------------------------------------------------------------------------
class _WebCallToolAction(CallToolAction):
    @field_validator("arguments", mode="before")
    @classmethod
    def _parse_string_arguments(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return {}
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return v


# Create base app (WebSocket, Playground, /health, /web)
app = create_app(
    EnterpriseArena,
    _WebCallToolAction,
    CallToolObservation,
    env_name="enterprise_arena",
)

# Remove framework's HTTP routes — use our singleton routes instead
_override_paths = {"/step", "/reset", "/state", "/"}
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


# ---------------------------------------------------------------------------
# Serve React landing page from /static build output
# ---------------------------------------------------------------------------
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if _STATIC_DIR.is_dir():
    # Serve the landing page at /
    @app.get("/", response_class=HTMLResponse)
    async def landing_page():
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index, media_type="text/html")
        return HTMLResponse("<h1>Enterprise Arena</h1><p><a href='/web/'>Open Playground</a></p>")

    # Mount static assets (JS/CSS bundles)
    _ASSETS_DIR = _STATIC_DIR / "assets"
    if _ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="static-assets")
else:
    # Fallback: no build output, redirect / to playground
    @app.get("/")
    async def landing_redirect():
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/web/")

# Convenience redirect: /playground → /web/
@app.get("/playground")
async def playground_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/web/")


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
