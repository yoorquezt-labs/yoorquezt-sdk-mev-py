"""Tests for MEVGatewayClient with httpx mock."""

import pytest
import pytest_httpx

from yoorquezt_mev.gateway import MEVGatewayClient
from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.types import Bundle


GW_URL = "http://localhost:9099"


@pytest.fixture
def gateway():
    return MEVGatewayClient(GW_URL, api_key="test-key")


def _rpc_response(result, request_id=1):
    """Helper to build a JSON-RPC response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(code, message, request_id=1):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


class TestSubmitBundle:
    async def test_submit_bundle(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response("bundle-abc123"),
        )
        bundle = Bundle(
            id="b1",
            transactions=["0xsigned1", "0xsigned2"],
            block_number=18_000_000,
        )
        result = await gateway.submit_bundle(bundle)
        assert result == "bundle-abc123"

    async def test_submit_bundle_rpc_error(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_error(-32000, "bundle simulation reverted"),
        )
        bundle = Bundle(id="b2", transactions=["0x1"], block_number=1)
        with pytest.raises(QMEVError) as exc_info:
            await gateway.submit_bundle(bundle)
        assert "reverted" in str(exc_info.value)


class TestGetBundleStatus:
    async def test_success(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({
                "bundle_id": "b1",
                "status": "landed",
                "block_number": 18_000_000,
                "profit": "50000000000000000",
                "gas_used": 150000,
            }),
        )
        status = await gateway.get_bundle_status("b1")
        assert status.status == "landed"
        assert status.profit == "50000000000000000"


class TestSimulateBundle:
    async def test_success(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({
                "success": True,
                "profit": "100000000000000000",
                "gas_used": 200000,
                "effective_gas_price": "30000000000",
                "logs": ["Transfer(...)"],
                "state_changes": [],
            }),
        )
        bundle = Bundle(id="b1", transactions=["0x1"], block_number=1)
        result = await gateway.simulate_bundle(bundle)
        assert result.success is True
        assert result.gas_used == 200000


class TestGetAuction:
    async def test_current_auction(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({
                "block_number": 18_000_000,
                "bids": [
                    {
                        "bidder": "0x1234",
                        "amount": "100000000000000000",
                        "bundle_hash": "0xhash",
                        "timestamp": 1700000000,
                    }
                ],
                "status": "open",
                "deadline": 1700000012,
            }),
        )
        auction = await gateway.get_auction()
        assert auction.status == "open"
        assert len(auction.bids) == 1

    async def test_auction_by_block(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({
                "block_number": 18_000_001,
                "bids": [],
                "status": "closed",
                "deadline": 1700000024,
            }),
        )
        auction = await gateway.get_auction(block_number=18_000_001)
        assert auction.block_number == 18_000_001
        assert auction.status == "closed"


class TestGetMempoolSnapshot:
    async def test_snapshot(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({
                "size": 5000,
                "pending_txs": 4800,
                "gas_stats": {
                    "min": "10000000000",
                    "max": "100000000000",
                    "avg": "30000000000",
                    "median": "25000000000",
                },
                "top_tokens": [
                    {"token": "WETH", "count": 1200},
                ],
            }),
        )
        snapshot = await gateway.get_mempool_snapshot()
        assert snapshot.size == 5000
        assert snapshot.gas_stats.avg == "30000000000"


class TestGetRelayStats:
    async def test_all_relays(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response([
                {
                    "relay_id": "r1",
                    "name": "Flashbots",
                    "url": "https://relay.flashbots.net",
                    "status": "active",
                    "bundles_submitted": 1000,
                    "bundles_landed": 950,
                    "avg_latency_ms": 45.0,
                    "success_rate": 0.95,
                    "last_seen": 1700000000,
                }
            ]),
        )
        stats = await gateway.get_relay_stats()
        assert len(stats) == 1
        assert stats[0].name == "Flashbots"


class TestGetProfitHistory:
    async def test_default(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({
                "time_range": "24h",
                "total_profit": "1000000000000000000",
                "total_cost": "200000000000000000",
                "net_profit": "800000000000000000",
                "bundle_count": 50,
                "success_rate": 0.92,
                "by_strategy": {},
                "data_points": [],
            }),
        )
        history = await gateway.get_profit_history()
        assert history.bundle_count == 50
        assert history.success_rate == 0.92


class TestRawCall:
    async def test_raw_call(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({"custom": "data"}),
        )
        result = await gateway.call("custom_method", ["arg1"])
        assert result == {"custom": "data"}

    async def test_http_error(self, httpx_mock: pytest_httpx.HTTPXMock, gateway: MEVGatewayClient):
        httpx_mock.add_response(url=GW_URL, status_code=500)
        with pytest.raises(QMEVError) as exc_info:
            await gateway.call("any_method")
        assert exc_info.value.code == "HTTP_ERROR"


class TestGatewayLifecycle:
    async def test_context_manager(self, httpx_mock: pytest_httpx.HTTPXMock):
        httpx_mock.add_response(
            url=GW_URL,
            json=_rpc_response({"size": 0, "pending_txs": 0, "gas_stats": {"min": "0", "max": "0", "avg": "0", "median": "0"}, "top_tokens": []}),
        )
        async with MEVGatewayClient(GW_URL) as gw:
            snapshot = await gw.get_mempool_snapshot()
            assert snapshot.size == 0

    async def test_trailing_slash_stripped(self):
        gw = MEVGatewayClient(f"{GW_URL}/")
        assert gw.url == GW_URL
        await gw.close()
