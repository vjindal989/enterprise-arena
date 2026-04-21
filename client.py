"""Lightweight client wrapper for the Enterprise Arena HTTP API."""

import os
import requests
from typing import Any, Dict, Optional


class EnterpriseArenaClient:
    """Client for interacting with the Enterprise Arena environment over HTTP."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or os.getenv("ENV_URL", "http://localhost:8000")).rstrip("/")
        self.session = requests.Session()

    def reset(self, task_id: str = "easy", **kwargs) -> Dict[str, Any]:
        payload = {"task_id": task_id, **kwargs}
        resp = self.session.post(f"{self.base_url}/reset", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def step(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        payload = {"action": {"tool_name": tool_name, "arguments": arguments or {}}}
        resp = self.session.post(f"{self.base_url}/step", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def state(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/state", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()
