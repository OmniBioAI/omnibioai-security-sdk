"""Direct-instantiation tests for policy/client.py PolicyClient."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_policy_evaluate_allow():
    with patch("policy.client.httpx") as mock_httpx:
        mock_http = AsyncMock()
        mock_httpx.AsyncClient.return_value = mock_http

        from policy.client import PolicyClient
        client = PolicyClient(base_url="http://policy:8002")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"allow": True, "reason": "ok"}
        client.http.post = AsyncMock(return_value=mock_resp)

        result = await client.evaluate(
            user={"user_id": "u1", "roles": ["researcher"]},
            path="/api/tes/submit",
            method="POST",
        )
        assert result["allow"] is True


@pytest.mark.asyncio
async def test_policy_evaluate_deny():
    with patch("policy.client.httpx") as mock_httpx:
        mock_http = AsyncMock()
        mock_httpx.AsyncClient.return_value = mock_http

        from policy.client import PolicyClient
        client = PolicyClient(base_url="http://policy:8002")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"allow": False, "reason": "forbidden"}
        client.http.post = AsyncMock(return_value=mock_resp)

        result = await client.evaluate(
            user={"user_id": "u2", "roles": []},
            path="/api/dataset/delete",
            method="DELETE",
        )
        assert result["allow"] is False


@pytest.mark.asyncio
async def test_policy_evaluate_posts_correct_payload():
    with patch("policy.client.httpx") as mock_httpx:
        mock_http = AsyncMock()
        mock_httpx.AsyncClient.return_value = mock_http

        from policy.client import PolicyClient
        client = PolicyClient(base_url="http://policy:8002")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"allow": True}
        client.http.post = AsyncMock(return_value=mock_resp)

        await client.evaluate(user={"user_id": "u1"}, path="/api/test", method="GET")

        call_args = client.http.post.call_args
        assert "/evaluate" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["path"] == "/api/test"
        assert payload["method"] == "GET"
