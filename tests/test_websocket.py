"""Tests for MEVGatewayClient WebSocket subscription lifecycle."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.gateway import MEVGatewayClient
from yoorquezt_mev.types import MEVEvent


GW_URL = "http://localhost:9099"
WS_URL = "ws://localhost:9099"


class FakeWebSocket:
    """A fake WebSocket that yields pre-loaded messages when iterated."""

    def __init__(self, messages: list[str] | None = None):
        self.messages = messages or []
        self.sent: list[str] = []
        self.closed = False

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for msg in self.messages:
            yield msg


def _make_ws_mock():
    """Create a mock WebSocket connection that can be iterated over."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    # By default yields nothing when iterated
    ws.__aiter__ = MagicMock(return_value=iter([]))
    return ws


class TestEnsureWebSocket:
    async def test_creates_ws_connection(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()

        with patch("yoorquezt_mev.gateway.websockets.connect", new_callable=AsyncMock, return_value=ws):
            with patch.object(gw, "_ws_listen", new_callable=AsyncMock):
                await gw._ensure_websocket()
                assert gw._ws is ws

        await gw.close()

    async def test_http_to_ws_url_conversion(self):
        gw = MEVGatewayClient("http://example.com:9099")
        ws = _make_ws_mock()

        with patch("yoorquezt_mev.gateway.websockets.connect", new_callable=AsyncMock, return_value=ws) as mock_connect:
            with patch.object(gw, "_ws_listen", new_callable=AsyncMock):
                await gw._ensure_websocket()
                mock_connect.assert_called_once()
                call_args = mock_connect.call_args
                assert call_args[0][0] == "ws://example.com:9099"

        await gw.close()

    async def test_https_to_wss_url_conversion(self):
        gw = MEVGatewayClient("https://secure.example.com")
        ws = _make_ws_mock()

        with patch("yoorquezt_mev.gateway.websockets.connect", new_callable=AsyncMock, return_value=ws) as mock_connect:
            with patch.object(gw, "_ws_listen", new_callable=AsyncMock):
                await gw._ensure_websocket()
                call_args = mock_connect.call_args
                assert call_args[0][0] == "wss://secure.example.com"

        await gw.close()

    async def test_api_key_sent_in_headers(self):
        gw = MEVGatewayClient(GW_URL, api_key="my-secret")
        ws = _make_ws_mock()

        with patch("yoorquezt_mev.gateway.websockets.connect", new_callable=AsyncMock, return_value=ws) as mock_connect:
            with patch.object(gw, "_ws_listen", new_callable=AsyncMock):
                await gw._ensure_websocket()
                call_kwargs = mock_connect.call_args.kwargs
                assert call_kwargs["additional_headers"]["Authorization"] == "Bearer my-secret"

        await gw.close()

    async def test_no_api_key_no_auth_header(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()

        with patch("yoorquezt_mev.gateway.websockets.connect", new_callable=AsyncMock, return_value=ws) as mock_connect:
            with patch.object(gw, "_ws_listen", new_callable=AsyncMock):
                await gw._ensure_websocket()
                call_kwargs = mock_connect.call_args.kwargs
                assert "Authorization" not in call_kwargs.get("additional_headers", {})

        await gw.close()

    async def test_does_not_reconnect_if_already_connected(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        gw._ws = ws  # already connected

        with patch("yoorquezt_mev.gateway.websockets.connect", new_callable=AsyncMock) as mock_connect:
            await gw._ensure_websocket()
            mock_connect.assert_not_called()

        await gw.close()

    async def test_connection_failure_raises_network_error(self):
        gw = MEVGatewayClient(GW_URL)

        with patch(
            "yoorquezt_mev.gateway.websockets.connect",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("refused"),
        ):
            with pytest.raises(QMEVError) as exc_info:
                await gw._ensure_websocket()
            assert exc_info.value.code == "NETWORK_ERROR"

        await gw.close()


class TestSubscribe:
    async def test_subscribe_returns_sub_id(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        gw._ws = ws

        with patch.object(gw, "_ensure_websocket", new_callable=AsyncMock):
            sub_id = await gw.subscribe(["bundles", "auctions"], lambda e: None)

        assert sub_id.startswith("sub_")
        assert sub_id in gw._subscription_handlers
        await gw.close()

    async def test_subscribe_sends_rpc_request(self):
        gw = MEVGatewayClient(GW_URL)
        ws = FakeWebSocket()
        gw._ws = ws

        with patch.object(gw, "_ensure_websocket", new_callable=AsyncMock):
            await gw.subscribe(["bundles"], lambda e: None)

        assert len(ws.sent) == 1
        sent = json.loads(ws.sent[0])
        assert sent["method"] == "mev_subscribe"
        assert sent["jsonrpc"] == "2.0"
        assert sent["params"][0]["topics"] == ["bundles"]

    async def test_multiple_subscriptions_have_unique_ids(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        gw._ws = ws

        with patch.object(gw, "_ensure_websocket", new_callable=AsyncMock):
            id1 = await gw.subscribe(["bundles"], lambda e: None)
            id2 = await gw.subscribe(["auctions"], lambda e: None)

        assert id1 != id2
        assert len(gw._subscription_handlers) == 2
        await gw.close()


class TestUnsubscribe:
    async def test_unsubscribe_removes_handler(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        gw._ws = ws
        gw._subscription_handlers["sub_1"] = lambda e: None

        await gw.unsubscribe("sub_1")
        assert "sub_1" not in gw._subscription_handlers
        await gw.close()

    async def test_unsubscribe_sends_rpc_request(self):
        gw = MEVGatewayClient(GW_URL)
        ws = FakeWebSocket()
        gw._ws = ws
        gw._subscription_handlers["sub_1"] = lambda e: None

        await gw.unsubscribe("sub_1")

        assert len(ws.sent) == 1
        sent = json.loads(ws.sent[0])
        assert sent["method"] == "mev_unsubscribe"
        assert sent["params"] == ["sub_1"]
        await gw.close()

    async def test_unsubscribe_nonexistent_is_noop(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        gw._ws = ws

        # Should not raise
        await gw.unsubscribe("sub_nonexistent")
        await gw.close()

    async def test_unsubscribe_handles_send_failure(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        ws.send = AsyncMock(side_effect=Exception("send failed"))
        gw._ws = ws
        gw._subscription_handlers["sub_1"] = lambda e: None

        # Should not raise despite send failure
        await gw.unsubscribe("sub_1")
        assert "sub_1" not in gw._subscription_handlers
        await gw.close()

    async def test_unsubscribe_without_ws_connection(self):
        gw = MEVGatewayClient(GW_URL)
        gw._subscription_handlers["sub_1"] = lambda e: None

        # No ws, should still remove handler without error
        await gw.unsubscribe("sub_1")
        assert "sub_1" not in gw._subscription_handlers
        await gw.close()


class TestWSListen:
    async def test_dispatches_event_to_sync_handler(self):
        gw = MEVGatewayClient(GW_URL)
        received_events: list[MEVEvent] = []

        def handler(event: MEVEvent):
            received_events.append(event)

        gw._subscription_handlers["sub_1"] = handler

        msg = json.dumps({
            "method": "mev_subscription",
            "params": {
                "subscriptionId": "sub_1",
                "event": {
                    "type": "bundle_landed",
                    "data": {"bundle_id": "b1", "profit": "100"},
                    "timestamp": 1700000000,
                },
            },
        })

        gw._ws = FakeWebSocket([msg])

        await gw._ws_listen()

        assert len(received_events) == 1
        assert received_events[0].type == "bundle_landed"
        assert received_events[0].data["bundle_id"] == "b1"

    async def test_dispatches_event_to_async_handler(self):
        gw = MEVGatewayClient(GW_URL)
        received_events: list[MEVEvent] = []

        async def handler(event: MEVEvent):
            received_events.append(event)

        gw._subscription_handlers["sub_1"] = handler

        msg = json.dumps({
            "method": "mev_subscription",
            "params": {
                "subscriptionId": "sub_1",
                "event": {
                    "type": "auction_closed",
                    "data": {"block": 18000000},
                    "timestamp": 1700000000,
                },
            },
        })

        gw._ws = FakeWebSocket([msg])

        await gw._ws_listen()

        assert len(received_events) == 1
        assert received_events[0].type == "auction_closed"

    async def test_ignores_malformed_json(self):
        gw = MEVGatewayClient(GW_URL)

        gw._ws = FakeWebSocket([
            "not json at all",
            '{"method": "mev_subscription", "params": {"subscriptionId": "sub_1", "event": {"type": "ok", "data": {}, "timestamp": 0}}}',
        ])

        received = []
        gw._subscription_handlers["sub_1"] = lambda e: received.append(e)

        await gw._ws_listen()
        assert len(received) == 1

    async def test_ignores_non_subscription_messages(self):
        gw = MEVGatewayClient(GW_URL)

        gw._ws = FakeWebSocket([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"}),
        ])

        # Should not raise
        await gw._ws_listen()

    async def test_ignores_unknown_subscription_id(self):
        gw = MEVGatewayClient(GW_URL)
        gw._subscription_handlers["sub_1"] = lambda e: None

        gw._ws = FakeWebSocket([
            json.dumps({
                "method": "mev_subscription",
                "params": {
                    "subscriptionId": "sub_999",  # not registered
                    "event": {"type": "x", "data": {}, "timestamp": 0},
                },
            }),
        ])

        # Should not raise
        await gw._ws_listen()

    async def test_multiple_events_dispatched(self):
        gw = MEVGatewayClient(GW_URL)
        events_1: list[MEVEvent] = []
        events_2: list[MEVEvent] = []
        gw._subscription_handlers["sub_1"] = lambda e: events_1.append(e)
        gw._subscription_handlers["sub_2"] = lambda e: events_2.append(e)

        gw._ws = FakeWebSocket([
            json.dumps({
                "method": "mev_subscription",
                "params": {
                    "subscriptionId": "sub_1",
                    "event": {"type": "a", "data": {}, "timestamp": 1},
                },
            }),
            json.dumps({
                "method": "mev_subscription",
                "params": {
                    "subscriptionId": "sub_2",
                    "event": {"type": "b", "data": {}, "timestamp": 2},
                },
            }),
            json.dumps({
                "method": "mev_subscription",
                "params": {
                    "subscriptionId": "sub_1",
                    "event": {"type": "c", "data": {}, "timestamp": 3},
                },
            }),
        ])

        await gw._ws_listen()

        assert len(events_1) == 2
        assert len(events_2) == 1
        assert events_1[0].type == "a"
        assert events_1[1].type == "c"
        assert events_2[0].type == "b"

    async def test_ws_set_to_none_after_listen_ends(self):
        gw = MEVGatewayClient(GW_URL)

        gw._ws = FakeWebSocket([])  # empty, ends immediately

        await gw._ws_listen()
        assert gw._ws is None


class TestClose:
    async def test_close_cancels_ws_task(self):
        gw = MEVGatewayClient(GW_URL)
        ws = _make_ws_mock()
        gw._ws = ws

        # Create a long-running task
        async def _long_running():
            await asyncio.sleep(100)

        gw._ws_task = asyncio.create_task(_long_running())
        gw._subscription_handlers["sub_1"] = lambda e: None

        await gw.close()

        assert gw._ws is None
        assert len(gw._subscription_handlers) == 0

    async def test_close_without_ws(self):
        gw = MEVGatewayClient(GW_URL)
        # Should not raise
        await gw.close()

    async def test_close_clears_subscription_handlers(self):
        gw = MEVGatewayClient(GW_URL)
        gw._subscription_handlers["a"] = lambda e: None
        gw._subscription_handlers["b"] = lambda e: None

        await gw.close()
        assert len(gw._subscription_handlers) == 0
