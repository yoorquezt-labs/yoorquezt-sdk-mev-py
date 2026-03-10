"""MEVGatewayClient — JSON-RPC + WebSocket client for the MEV Gateway."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from yoorquezt_mev.errors import QMEVError
from yoorquezt_mev.types import (
    Auction,
    Bundle,
    BundleStatus,
    JsonRpcRequest,
    JsonRpcResponse,
    MEVEvent,
    MempoolSnapshot,
    OFAStats,
    ProfitHistory,
    RelayStats,
    SimulationResult,
)


class MEVGatewayClient:
    """Async client for the MEV Gateway JSON-RPC API.

    Usage:
        async with MEVGatewayClient("http://localhost:9099") as gw:
            status = await gw.get_bundle_status("bundle-123")
            auction = await gw.get_auction()
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self._next_id = 1
        self._timeout = timeout
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)
        self._ws: ClientConnection | None = None
        self._subscription_handlers: dict[str, Any] = {}
        self._ws_task: asyncio.Task[None] | None = None

    # --- Bundle operations ---

    async def submit_bundle(self, bundle: Bundle) -> str:
        """Submit a bundle to the MEV engine. Returns the bundle ID."""
        return await self.call("mev_submitBundle", [bundle.model_dump()])

    async def get_bundle_status(self, bundle_id: str) -> BundleStatus:
        """Get the status of a previously submitted bundle."""
        data = await self.call("mev_getBundleStatus", [bundle_id])
        return BundleStatus.model_validate(data)

    async def simulate_bundle(self, bundle: Bundle) -> SimulationResult:
        """Simulate a bundle without submitting it."""
        data = await self.call("mev_simulateBundle", [bundle.model_dump()])
        return SimulationResult.model_validate(data)

    # --- Auction ---

    async def get_auction(self, block_number: int | None = None) -> Auction:
        """Get current auction state, optionally for a specific block."""
        params: list[Any] = [block_number] if block_number is not None else []
        data = await self.call("mev_getAuction", params)
        return Auction.model_validate(data)

    # --- Mempool ---

    async def get_mempool_snapshot(self) -> MempoolSnapshot:
        """Get a snapshot of the current mempool state."""
        data = await self.call("mev_getMempoolSnapshot")
        return MempoolSnapshot.model_validate(data)

    # --- Relay ---

    async def get_relay_stats(
        self, relay_id: str | None = None
    ) -> list[RelayStats]:
        """Get relay statistics, optionally filtered by relay ID."""
        params: list[Any] = [relay_id] if relay_id else []
        data = await self.call("mev_getRelayStats", params)
        return [RelayStats.model_validate(r) for r in data]

    # --- OFA ---

    async def get_ofa_stats(self, time_range: str | None = None) -> OFAStats:
        """Get Order Flow Auction statistics."""
        params: list[Any] = [time_range] if time_range else []
        data = await self.call("mev_getOFAStats", params)
        return OFAStats.model_validate(data)

    # --- Analytics ---

    async def get_profit_history(
        self,
        time_range: str = "24h",
        strategy: str | None = None,
    ) -> ProfitHistory:
        """Get profit history, optionally filtered by strategy."""
        params: list[Any] = [time_range]
        if strategy:
            params.append(strategy)
        data = await self.call("mev_getProfitHistory", params)
        return ProfitHistory.model_validate(data)

    # --- WebSocket subscriptions ---

    async def subscribe(
        self,
        topics: list[str],
        on_event: Any,
    ) -> str:
        """Subscribe to MEV event topics over WebSocket.

        Returns a subscription ID that can be used to unsubscribe.
        """
        await self._ensure_websocket()

        sub_id = f"sub_{self._next_id}"
        self._next_id += 1
        self._subscription_handlers[sub_id] = on_event

        request = JsonRpcRequest(
            id=self._next_id,
            method="mev_subscribe",
            params=[{"topics": topics, "subscriptionId": sub_id}],
        )
        self._next_id += 1

        if self._ws:
            await self._ws.send(request.model_dump_json())

        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a previously created subscription."""
        self._subscription_handlers.pop(subscription_id, None)
        if self._ws:
            request = JsonRpcRequest(
                id=self._next_id,
                method="mev_unsubscribe",
                params=[subscription_id],
            )
            self._next_id += 1
            try:
                await self._ws.send(request.model_dump_json())
            except Exception:
                pass

    # --- Raw JSON-RPC ---

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        """Execute a raw JSON-RPC call against the gateway."""
        request_id = self._next_id
        self._next_id += 1

        request = JsonRpcRequest(
            id=request_id,
            method=method,
            params=params or [],
        )

        try:
            response = await self._client.post(
                self.url, content=request.model_dump_json()
            )
        except httpx.HTTPError as exc:
            raise QMEVError.network_error(exc) from exc

        if response.status_code >= 400:
            raise QMEVError(
                "HTTP_ERROR",
                f"Gateway request failed: {response.status_code}",
            )

        rpc_response = JsonRpcResponse.model_validate(response.json())

        if rpc_response.error:
            raise QMEVError.from_json_rpc_error(rpc_response.error)

        return rpc_response.result

    async def close(self) -> None:
        """Close all connections."""
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._subscription_handlers.clear()
        await self._client.aclose()

    async def __aenter__(self) -> MEVGatewayClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # --- Internal ---

    async def _ensure_websocket(self) -> None:
        if self._ws is not None:
            return

        ws_url = self.url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        extra_headers: dict[str, str] = {}
        if self.api_key:
            extra_headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            self._ws = await websockets.connect(
                ws_url, additional_headers=extra_headers
            )
        except Exception as exc:
            raise QMEVError.network_error(exc) from exc

        self._ws_task = asyncio.create_task(self._ws_listen())

    async def _ws_listen(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Handle subscription notifications
                if msg.get("method") == "mev_subscription" and "params" in msg:
                    sub_id = msg["params"].get("subscriptionId")
                    handler = self._subscription_handlers.get(sub_id)
                    if handler:
                        event = MEVEvent.model_validate(msg["params"]["event"])
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
        except websockets.ConnectionClosed:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            self._ws = None
