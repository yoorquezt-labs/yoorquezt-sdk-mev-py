"""Tests for QMEVClient with httpx mock."""

import pytest
import httpx
import pytest_httpx

from yoorquezt_mev.client import QMEVClient
from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.types import MEVRole


API_URL = "https://api.test.com"
API_KEY = "sk-test-key"


@pytest.fixture
def client():
    return QMEVClient(API_URL, API_KEY, role=MEVRole.SEARCHER)


class TestHealth:
    async def test_health_success(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(
            url=f"{API_URL}/health",
            json={
                "status": "healthy",
                "uptime": 86400,
                "version": "1.0.0",
                "chain_id": 1,
                "block_number": 18000000,
                "peer_count": 50,
                "mempool_size": 5000,
                "bundle_count": 100,
                "active_relays": 3,
                "last_block_time": 1700000000,
            },
        )
        health = await client.health()
        assert health.status == "healthy"
        assert health.chain_id == 1
        assert health.block_number == 18000000

    async def test_health_auth_error(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(url=f"{API_URL}/health", status_code=401)
        with pytest.raises(QMEVError) as exc_info:
            await client.health()
        assert exc_info.value.code == "AUTH_INVALID"

    async def test_health_server_error(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(
            url=f"{API_URL}/health",
            status_code=500,
            json={"error": "internal"},
        )
        with pytest.raises(QMEVError) as exc_info:
            await client.health()
        assert exc_info.value.code == "HTTP_ERROR"


class TestChat:
    async def test_chat_success(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(
            url=f"{API_URL}/v1/chat",
            json={
                "message": "MEV stands for Maximal Extractable Value.",
                "conversation_id": "conv-123",
            },
        )
        resp = await client.chat("What is MEV?")
        assert "MEV" in resp.message
        assert resp.conversation_id == "conv-123"
        assert resp.tools_called is None

    async def test_chat_with_conversation_id(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(
            url=f"{API_URL}/v1/chat",
            json={
                "message": "Sure, here is more detail.",
                "conversation_id": "conv-123",
            },
        )
        resp = await client.chat("Tell me more", conversation_id="conv-123")
        assert resp.conversation_id == "conv-123"

    async def test_chat_with_tools(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(
            url=f"{API_URL}/v1/chat",
            json={
                "message": "The current auction is open.",
                "conversation_id": "conv-456",
                "tools_called": [
                    {"tool_name": "get_auction", "success": True, "result": {"status": "open"}}
                ],
            },
        )
        resp = await client.chat("Show me the auction")
        assert resp.tools_called is not None
        assert len(resp.tools_called) == 1
        assert resp.tools_called[0].tool_name == "get_auction"


class TestListTools:
    async def test_list_tools(self, httpx_mock: pytest_httpx.HTTPXMock, client: QMEVClient):
        httpx_mock.add_response(
            url=f"{API_URL}/v1/tools",
            json=[
                {
                    "name": "get_auction",
                    "description": "Get current auction state",
                    "parameters": {"block_number": {"type": "integer"}},
                },
                {
                    "name": "submit_bundle",
                    "description": "Submit a bundle",
                    "parameters": {"bundle": {"type": "object"}},
                },
            ],
        )
        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "get_auction"


class TestClientLifecycle:
    async def test_context_manager(self, httpx_mock: pytest_httpx.HTTPXMock):
        httpx_mock.add_response(
            url=f"{API_URL}/health",
            json={
                "status": "healthy",
                "uptime": 0,
                "version": "1.0.0",
                "chain_id": 1,
                "block_number": 0,
                "peer_count": 0,
                "mempool_size": 0,
                "active_relays": 0,
            },
        )
        async with QMEVClient(API_URL, API_KEY) as c:
            h = await c.health()
            assert h.status == "healthy"

    async def test_default_role(self):
        c = QMEVClient(API_URL, API_KEY)
        assert c.role == MEVRole.ANALYST
        await c.close()

    async def test_trailing_slash_stripped(self):
        c = QMEVClient(f"{API_URL}/", API_KEY)
        assert c.api_url == API_URL
        await c.close()
