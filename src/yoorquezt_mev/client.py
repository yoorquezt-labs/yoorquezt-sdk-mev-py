"""QMEVClient — async HTTP client for Q MEV AI API."""

from __future__ import annotations

from typing import Any

import httpx

from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.streaming import stream_chat, stream_chat_full
from yoorquezt_mev.types import ChatResponse, EngineHealth, MEVRole, QMEVTool


class QMEVClient:
    """Async client for the Q MEV AI API.

    Usage:
        async with QMEVClient("https://api.example.com", "sk-...") as client:
            health = await client.health()
            resp = await client.chat("What is MEV?")
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        role: MEVRole = MEVRole.ANALYST,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.role = role
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    async def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Send a chat message and receive a complete response."""
        body: dict[str, Any] = {
            "message": message,
            "role": self.role.value,
        }
        if conversation_id:
            body["conversationId"] = conversation_id
        if context:
            body["context"] = context

        data = await self._request("POST", "/v1/chat", json=body)
        return ChatResponse.model_validate(data)

    async def chat_stream(
        self,
        message: str,
        conversation_id: str | None = None,
        on_token: Any = None,
    ) -> ChatResponse:
        """Stream a chat response, optionally calling on_token per token.

        Returns the complete ChatResponse after the stream finishes.
        """
        return await stream_chat_full(
            self.api_url,
            self.api_key,
            message,
            on_token=on_token,
            conversation_id=conversation_id,
            role=self.role,
        )

    def chat_stream_iter(
        self,
        message: str,
        conversation_id: str | None = None,
    ):
        """Return an async iterator that yields tokens as they arrive.

        Usage:
            async for token in client.chat_stream_iter("What is MEV?"):
                print(token, end="")
        """
        return stream_chat(
            self.api_url,
            self.api_key,
            message,
            conversation_id=conversation_id,
            role=self.role,
        )

    async def list_tools(self) -> list[QMEVTool]:
        """List all available Q MEV tools."""
        data = await self._request("GET", "/v1/tools")
        return [QMEVTool.model_validate(t) for t in data]

    async def health(self) -> EngineHealth:
        """Get the current engine health status."""
        data = await self._request("GET", "/health")
        return EngineHealth.model_validate(data)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> QMEVClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_url}{path}"
        try:
            response = await self._client.request(
                method, url, json=json, params=params
            )
        except httpx.HTTPError as exc:
            raise QMEVError.network_error(exc) from exc

        if response.status_code in (401, 403):
            raise QMEVError.auth_error()

        if response.status_code >= 400:
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text
            raise QMEVError(
                "HTTP_ERROR",
                f"Request failed: {method} {path} => {response.status_code}",
                error_body,
            )

        return response.json()
