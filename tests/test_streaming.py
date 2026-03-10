"""Tests for SSE streaming client (stream_chat and stream_chat_full)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.streaming import stream_chat, stream_chat_full
from yoorquezt_mev.types import MEVRole


API_URL = "https://api.test.com"
API_KEY = "sk-test-key"


def _sse_lines(*events: dict | str) -> list[str]:
    """Build SSE lines from event dicts or raw strings.

    Each dict is serialized as ``data: <json>``.
    The string ``"[DONE]"`` becomes ``data: [DONE]``.
    Plain strings are passed through verbatim (for testing non-data lines).
    """
    lines: list[str] = []
    for ev in events:
        if isinstance(ev, dict):
            lines.append(f"data: {json.dumps(ev)}")
        elif ev == "[DONE]":
            lines.append("data: [DONE]")
        else:
            lines.append(ev)
    return lines


def _mock_stream_response(
    lines: list[str],
    status_code: int = 200,
):
    """Create a mock that replaces ``httpx.AsyncClient.stream`` as an async context manager.

    The mock response exposes ``aiter_lines`` yielding the provided *lines* and
    ``aread`` returning the joined text (used on error paths).
    """
    response = AsyncMock()
    response.status_code = status_code

    async def _aiter_lines():
        for line in lines:
            yield line

    response.aiter_lines = _aiter_lines
    response.aread = AsyncMock(return_value=b"error body")

    # Make the response usable as an async context manager
    stream_cm = AsyncMock()
    stream_cm.__aenter__ = AsyncMock(return_value=response)
    stream_cm.__aexit__ = AsyncMock(return_value=False)

    return stream_cm, response


# ---------------------------------------------------------------------------
# stream_chat — token-by-token async generator
# ---------------------------------------------------------------------------


class TestStreamChat:
    async def test_yields_tokens(self):
        lines = _sse_lines(
            {"type": "token", "token": "Hello"},
            {"type": "token", "token": " world"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            tokens = []
            async for token in stream_chat(API_URL, API_KEY, "hi"):
                tokens.append(token)

            assert tokens == ["Hello", " world"]

    async def test_skips_non_data_lines(self):
        lines = _sse_lines(
            ": keep-alive",  # comment line
            "",  # blank line
            {"type": "token", "token": "ok"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            tokens = [t async for t in stream_chat(API_URL, API_KEY, "hi")]
            assert tokens == ["ok"]

    async def test_skips_malformed_json(self):
        lines = [
            "data: {invalid json",
            'data: {"type": "token", "token": "good"}',
            "data: [DONE]",
        ]
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            tokens = [t async for t in stream_chat(API_URL, API_KEY, "hi")]
            assert tokens == ["good"]

    async def test_skips_non_token_events(self):
        lines = _sse_lines(
            {"type": "meta", "info": "something"},
            {"type": "token", "token": "actual"},
            {"type": "done", "conversationId": "c1"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            tokens = [t async for t in stream_chat(API_URL, API_KEY, "hi")]
            assert tokens == ["actual"]

    async def test_error_event_raises(self):
        lines = _sse_lines(
            {"type": "token", "token": "before"},
            {"type": "error", "message": "rate limit exceeded"},
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                async for _ in stream_chat(API_URL, API_KEY, "hi"):
                    pass
            assert exc_info.value.code == "STREAM_ERROR"
            assert "rate limit" in str(exc_info.value)

    async def test_error_event_without_message(self):
        lines = _sse_lines({"type": "error"})
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                async for _ in stream_chat(API_URL, API_KEY, "hi"):
                    pass
            assert "Stream error" in str(exc_info.value)

    async def test_auth_error_401(self):
        cm, _ = _mock_stream_response([], status_code=401)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                async for _ in stream_chat(API_URL, API_KEY, "hi"):
                    pass
            assert exc_info.value.code == "AUTH_INVALID"

    async def test_auth_error_403(self):
        cm, _ = _mock_stream_response([], status_code=403)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                async for _ in stream_chat(API_URL, API_KEY, "hi"):
                    pass
            assert exc_info.value.code == "AUTH_INVALID"

    async def test_http_error_500(self):
        cm, _ = _mock_stream_response([], status_code=500)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                async for _ in stream_chat(API_URL, API_KEY, "hi"):
                    pass
            assert exc_info.value.code == "STREAM_ERROR"

    async def test_network_error(self):
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            # stream() itself raises an httpx.ConnectError
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
            cm.__aexit__ = AsyncMock(return_value=False)
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                async for _ in stream_chat(API_URL, API_KEY, "hi"):
                    pass
            assert exc_info.value.code == "NETWORK_ERROR"

    async def test_conversation_id_passed_in_body(self):
        lines = _sse_lines("[DONE]")
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            async for _ in stream_chat(
                API_URL, API_KEY, "hi", conversation_id="conv-1"
            ):
                pass

            # Verify stream() was called with json body containing conversationId
            call_kwargs = instance.stream.call_args
            assert call_kwargs is not None
            body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert body["conversationId"] == "conv-1"

    async def test_role_passed_in_body(self):
        lines = _sse_lines("[DONE]")
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            async for _ in stream_chat(
                API_URL, API_KEY, "hi", role=MEVRole.SEARCHER
            ):
                pass

            call_kwargs = instance.stream.call_args
            body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert body["role"] == "searcher"

    async def test_empty_stream_yields_nothing(self):
        lines = _sse_lines("[DONE]")
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            tokens = [t async for t in stream_chat(API_URL, API_KEY, "hi")]
            assert tokens == []

    async def test_token_event_missing_token_field_skipped(self):
        """A 'token' type event without the 'token' key should be skipped."""
        lines = _sse_lines(
            {"type": "token"},  # missing "token" key
            {"type": "token", "token": "ok"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            tokens = [t async for t in stream_chat(API_URL, API_KEY, "hi")]
            assert tokens == ["ok"]


# ---------------------------------------------------------------------------
# stream_chat_full — collects full response
# ---------------------------------------------------------------------------


class TestStreamChatFull:
    async def test_collects_full_message(self):
        lines = _sse_lines(
            {"type": "token", "token": "Hello"},
            {"type": "token", "token": " "},
            {"type": "token", "token": "world"},
            {"type": "done", "conversationId": "conv-99"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await stream_chat_full(API_URL, API_KEY, "hi")
            assert result.message == "Hello world"
            assert result.conversation_id == "conv-99"
            assert result.tools_called is None

    async def test_on_token_callback_called(self):
        lines = _sse_lines(
            {"type": "token", "token": "a"},
            {"type": "token", "token": "b"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            callback = MagicMock()
            result = await stream_chat_full(
                API_URL, API_KEY, "hi", on_token=callback
            )
            assert result.message == "ab"
            assert callback.call_count == 2
            callback.assert_any_call("a")
            callback.assert_any_call("b")

    async def test_done_event_with_tools(self):
        lines = _sse_lines(
            {"type": "token", "token": "done"},
            {
                "type": "done",
                "conversationId": "c1",
                "toolsCalled": [
                    {"toolName": "get_auction", "success": True, "result": {"status": "open"}},
                    {"toolName": "get_bundle", "success": False},
                ],
            },
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await stream_chat_full(API_URL, API_KEY, "hi")
            assert result.tools_called is not None
            assert len(result.tools_called) == 2
            assert result.tools_called[0].tool_name == "get_auction"
            assert result.tools_called[0].success is True
            assert result.tools_called[1].success is False

    async def test_error_event_raises(self):
        lines = _sse_lines(
            {"type": "token", "token": "partial"},
            {"type": "error", "message": "server overloaded"},
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                await stream_chat_full(API_URL, API_KEY, "hi")
            assert exc_info.value.code == "STREAM_ERROR"

    async def test_http_error_status(self):
        cm, _ = _mock_stream_response([], status_code=502)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                await stream_chat_full(API_URL, API_KEY, "hi")
            assert exc_info.value.code == "STREAM_ERROR"

    async def test_network_error(self):
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(
                side_effect=httpx.ConnectError("connection refused")
            )
            cm.__aexit__ = AsyncMock(return_value=False)
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            with pytest.raises(QMEVError) as exc_info:
                await stream_chat_full(API_URL, API_KEY, "hi")
            assert exc_info.value.code == "NETWORK_ERROR"

    async def test_malformed_json_skipped(self):
        lines = [
            "data: not json at all",
            'data: {"type": "token", "token": "ok"}',
            "data: [DONE]",
        ]
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await stream_chat_full(API_URL, API_KEY, "hi")
            assert result.message == "ok"

    async def test_no_done_event_uses_defaults(self):
        """When the stream ends without a 'done' event, defaults are used."""
        lines = _sse_lines(
            {"type": "token", "token": "partial"},
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await stream_chat_full(API_URL, API_KEY, "hi")
            assert result.message == "partial"
            assert result.conversation_id == ""
            assert result.tools_called is None

    async def test_preserves_existing_conversation_id(self):
        """When conversation_id is provided and done event has none, keep the original."""
        lines = _sse_lines(
            {"type": "token", "token": "x"},
            {"type": "done"},  # no conversationId in done
            "[DONE]",
        )
        cm, _ = _mock_stream_response(lines)
        with patch("yoorquezt_mev.streaming.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.stream = MagicMock(return_value=cm)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await stream_chat_full(
                API_URL, API_KEY, "hi", conversation_id="orig-conv"
            )
            assert result.conversation_id == "orig-conv"
