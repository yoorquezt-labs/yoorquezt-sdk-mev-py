"""Pydantic models for Q MEV AI SDK types."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class MEVRole(str, Enum):
    SEARCHER = "searcher"
    BUILDER = "builder"
    VALIDATOR = "validator"
    OPERATOR = "operator"
    ANALYST = "analyst"


class Bundle(BaseModel):
    id: str
    transactions: list[str]
    block_number: int
    min_timestamp: int | None = None
    max_timestamp: int | None = None
    reverting_tx_hashes: list[str] | None = None


class BundleStatus(BaseModel):
    bundle_id: str
    status: str  # pending, submitted, landed, failed, cancelled
    block_number: int | None = None
    tx_hash: str | None = None
    profit: str | None = None
    gas_used: int | None = None
    error: str | None = None


class AuctionBid(BaseModel):
    bidder: str
    amount: str
    bundle_hash: str
    timestamp: int


class Auction(BaseModel):
    block_number: int
    bids: list[AuctionBid]
    winner: str | None = None
    winning_bid: str | None = None
    status: str  # open, closed, finalized
    deadline: int


class RelayStats(BaseModel):
    relay_id: str
    name: str
    url: str
    status: str  # active, inactive, degraded
    bundles_submitted: int
    bundles_landed: int
    avg_latency_ms: float
    success_rate: float
    last_seen: int


class GasStats(BaseModel):
    min: str
    max: str
    avg: str
    median: str


class TokenCount(BaseModel):
    token: str
    count: int


class MempoolSnapshot(BaseModel):
    size: int
    pending_txs: int
    gas_stats: GasStats
    top_tokens: list[TokenCount]


class EngineHealth(BaseModel):
    status: str  # healthy, degraded, unhealthy
    uptime: int
    version: str
    chain_id: int
    block_number: int
    peer_count: int
    mempool_size: int
    bundle_count: int = 0
    active_relays: int
    last_block_time: int = 0


class StrategyProfit(BaseModel):
    profit: str
    count: int


class ProfitDataPoint(BaseModel):
    timestamp: int
    profit: str


class ProfitHistory(BaseModel):
    time_range: str
    total_profit: str
    total_cost: str
    net_profit: str
    bundle_count: int
    success_rate: float
    by_strategy: dict[str, StrategyProfit]
    data_points: list[ProfitDataPoint]


class StateChange(BaseModel):
    address: str
    key: str
    before: str
    after: str


class SimulationResult(BaseModel):
    success: bool
    profit: str
    gas_used: int
    effective_gas_price: str
    logs: list[str]
    state_changes: list[StateChange]
    error: str | None = None


class OFAStats(BaseModel):
    txs_protected: int
    sandwich_blocked: int
    mev_captured: str
    user_rebates: str
    rebate_rate: float
    avg_savings_per_tx: str


class MEVEvent(BaseModel):
    type: str
    data: dict[str, Any]
    timestamp: int


class ToolCall(BaseModel):
    tool_name: str
    success: bool
    result: Any | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    tools_called: list[ToolCall] | None = None


class QMEVTool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int
    method: str
    params: list[Any] | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: int
    result: Any | None = None
    error: dict[str, Any] | None = None
