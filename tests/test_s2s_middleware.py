"""TestClient-based integration tests for middleware/s2s.py ServiceAuthMiddleware."""
import sys
import types
import importlib
import jwt
import pytest
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
        "iam", "iam.client", "iam.cache",
        "core", "core.context", "core.config",
        "policy", "policy.client",
        "middleware", "middleware.s2s",
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

from middleware.s2s import ServiceAuthMiddleware  # noqa: E402

SECRET = "test-secret"
SERVICE = "workbench"


def _make_app():
    async def endpoint(request):
        return JSONResponse({"service": request.state.service})
    app = Starlette(routes=[Route("/test", endpoint)])
    app.add_middleware(ServiceAuthMiddleware, secret=SECRET, service_name=SERVICE)
    return app


def _token(service="tes", aud=None):
    return jwt.encode({"service": service, "aud": aud or [SERVICE]}, SECRET, algorithm="HS256")


def test_s2s_missing_token():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/test")
    assert resp.status_code == 401
    assert "missing service token" in resp.json()["error"]


def test_s2s_invalid_token():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/test", headers={"X-Service-Token": "bad.token"})
    assert resp.status_code == 401
    assert "invalid service token" in resp.json()["error"]


def test_s2s_wrong_audience():
    token = _token(aud=["other-service"])
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/test", headers={"X-Service-Token": token})
    assert resp.status_code == 403
    assert "service not allowed" in resp.json()["error"]


def test_s2s_valid_token_passes():
    token = _token(service="tes", aud=[SERVICE])
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/test", headers={"X-Service-Token": token})
    assert resp.status_code == 200
    assert resp.json()["service"] == "tes"
