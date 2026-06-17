"""TestClient-based integration tests for middleware/policy.py PolicyMiddleware."""
import sys
import types
import importlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


# Bridge omnibioai_security_sdk namespace so middleware imports resolve
def _ensure_sdk_namespace():
    if "omnibioai_security_sdk" in sys.modules:
        return
    root_ns = types.ModuleType("omnibioai_security_sdk")
    sub_names = [
        "core", "core.context",
        "policy", "policy.client",
        "middleware", "middleware.policy",
    ]
    for name in sub_names:
        parts = name.split(".")
        try:
            real = importlib.import_module(".".join(parts))
        except Exception:
            real = types.ModuleType(f"omnibioai_security_sdk.{name}")
        sys.modules[f"omnibioai_security_sdk.{name}"] = real
    sys.modules["omnibioai_security_sdk"] = root_ns

_ensure_sdk_namespace()

from middleware.policy import PolicyMiddleware  # noqa: E402


def _make_app(policy_client):
    async def endpoint(request):
        return JSONResponse({"ok": True})
    app = Starlette(routes=[Route("/test", endpoint)])
    app.add_middleware(PolicyMiddleware, policy=policy_client)
    return app


def test_policy_middleware_allows():
    mock_policy = MagicMock()
    mock_policy.evaluate = AsyncMock(return_value={"allow": True, "reason": "ok"})
    app = _make_app(mock_policy)
    client = TestClient(app, raise_server_exceptions=False)
    with patch("middleware.policy.get_user", return_value={"user_id": "u1", "roles": ["researcher"]}):
        resp = client.get("/test")
    assert resp.status_code == 200


def test_policy_middleware_denies():
    mock_policy = MagicMock()
    mock_policy.evaluate = AsyncMock(return_value={"allow": False, "reason": "forbidden"})
    app = _make_app(mock_policy)
    client = TestClient(app, raise_server_exceptions=False)
    with patch("middleware.policy.get_user", return_value={"user_id": "u2", "roles": []}):
        resp = client.get("/test")
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"
    assert resp.json()["reason"] == "forbidden"
