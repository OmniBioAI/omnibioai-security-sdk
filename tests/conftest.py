"""Shared pytest fixtures for the omnibioai-security-sdk test suite.

Provides mock Redis/HTTP transports and pre-wired IAMClient/PolicyClient
instances so individual test modules don't each reimplement the
dependency-patching boilerplate.

Developer: Manish Kumar <manish@omnibioai.org>
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_async_redis():
    """Provide a bare AsyncMock standing in for an async Redis client."""
    return AsyncMock()


@pytest.fixture
def mock_http():
    """Provide a bare AsyncMock standing in for an async HTTP client."""
    return AsyncMock()


@pytest.fixture
def iam_client_setup(mock_async_redis, mock_http):
    """Construct an IAMClient with its redis/httpx dependencies patched out.

    Yields (client, mock_redis, mock_http) so callers can pre-program cache
    and remote-validation responses without touching real infrastructure.
    """
    with patch("iam.client.redis") as mock_redis_module, \
         patch("iam.client.httpx") as mock_httpx:
        mock_redis_module.from_url.return_value = mock_async_redis
        mock_httpx.AsyncClient.return_value = mock_http
        from iam.client import IAMClient
        client = IAMClient(base_url="http://test-iam", redis_url="redis://localhost")
        client.redis = mock_async_redis
        client.http = mock_http
        yield client, mock_async_redis, mock_http


@pytest.fixture
def policy_client_setup(mock_http):
    """Construct a PolicyClient with its httpx dependency patched out.

    Yields (client, mock_http) so callers can pre-program policy-decision
    responses without a real policy engine.
    """
    with patch("policy.client.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_http
        from policy.client import PolicyClient
        client = PolicyClient(base_url="http://test-policy")
        client.http = mock_http
        yield client, mock_http
