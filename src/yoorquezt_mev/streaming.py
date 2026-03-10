"""SSE streaming client for Q MEV AI chat."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.types import ChatResponse, MEVRole, ToolCall


async def stream_chat(
    api_url: str,
    api_key: str,
    message: str,
    *,
    conversation_id: str | None = None,
    role: MEVRole = MEVRole.ANALYST,
) -> AsyncIterator[str]:
    """Stream a chat response from Q MEV AI as an async generator yielding tokens.

    Usage:
        async for token in stream_chat(url, key, "What is MEV?"):
            print(token, end="", flush=True)
    """
    url = f"{api_url.rstrip('/')}/v1/chat/stream"
    body: dict[str, Any] = {
        "message": message,
        "role": role.value,
    }
    if conversation_id:
        body["conversationId"] = conversation_id

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST", url, json=body, headers=headers, timeout=120.0
            ) as response:
                if response.status_code == 401 or response.status_code == 403:
                    raise QMEVError.auth_error()
                if response.status_code >= 400:
                    text = await response.aread()
                    raise QMEVError(
                        "STREAM_ERROR",
                        f"Stream request failed with status {response.status_code}: {text.decode()}",
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break

                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    if event.get("type") == "token" and "token" in event:
                        yield event["token"]
                    elif event.get("type") == "error":
                        raise QMEVError(
                            "STREAM_ERROR",
                            event.get("message", "Stream error"),
                        )
        except httpx.HTTPError as exc:
            raise QMEVError.network_error(exc) from exc


async def stream_chat_full(
    api_url: str,
    api_key: str,
    message: str,
    on_token: Any = None,
    *,
    conversation_id: str | None = None,
    role: MEVRole = MEVRole.ANALYST,
) -> ChatResponse:
    """Stream chat and collect the full response, optionally calling on_token per token.

    Returns the complete ChatResponse after the stream finishes.
    """
    url = f"{api_url.rstrip('/')}/v1/chat/stream"
    body: dict[str, Any] = {
        "message": message,
        "role": role.value,
    }
    if conversation_id:
        body["conversationId"] = conversation_id

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    full_message = ""
    result_conversation_id = conversation_id or ""
    tools_called: list[ToolCall] | None = None

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST", url, json=body, headers=headers, timeout=120.0
            ) as response:
                if response.status_code >= 400:
                    text = await response.aread()
                    raise QMEVError(
                        "STREAM_ERROR",
                        f"Stream request failed: {response.status_code}: {text.decode()}",
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break

                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    if event.get("type") == "token" and "token" in event:
                        token = event["token"]
                        full_message += token
                        if on_token:
                            on_token(token)
                    elif event.get("type") == "done":
                        result_conversation_id = event.get(
                            "conversationId", result_conversation_id
                        )
                        raw_tools = event.get("toolsCalled")
                        if raw_tools:
                            tools_called = [
                                ToolCall(
                                    tool_name=t["toolName"],
                                    success=t["success"],
                                    result=t.get("result"),
                                )
                                for t in raw_tools
                            ]
                    elif event.get("type") == "error":
                        raise QMEVError(
                            "STREAM_ERROR",
                            event.get("message", "Stream error"),
                        )
        except httpx.HTTPError as exc:
            raise QMEVError.network_error(exc) from exc

    return ChatResponse(
        message=full_message,
        conversation_id=result_conversation_id,
        tools_called=tools_called,
    )
