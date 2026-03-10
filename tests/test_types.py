"""Tests for Pydantic model validation."""

import pytest
from pydantic import ValidationError

from yoorquezt_mev.types import (
    Auction,
    AuctionBid,
    Bundle,
    BundleStatus,
    ChatResponse,
    EngineHealth,
    GasStats,
    MEVEvent,
    MEVRole,
    MempoolSnapshot,
    OFAStats,
    ProfitHistory,
    RelayStats,
    SimulationResult,
    TokenCount,
)


class TestBundle:
    def test_valid_bundle(self):
        b = Bundle(
            id="bundle-1",
            transactions=["0xabc", "0xdef"],
            block_number=18_000_000,
        )
        assert b.id == "bundle-1"
        assert len(b.transactions) == 2
        assert b.block_number == 18_000_000
        assert b.min_timestamp is None

    def test_bundle_with_optional_fields(self):
        b = Bundle(
            id="bundle-2",
            transactions=["0x123"],
            block_number=18_000_001,
            min_timestamp=1700000000,
            max_timestamp=1700000060,
            reverting_tx_hashes=["0xfail"],
        )
        assert b.min_timestamp == 1700000000
        assert b.reverting_tx_hashes == ["0xfail"]

    def test_bundle_missing_required(self):
        with pytest.raises(ValidationError):
            Bundle(id="x", transactions=["0xabc"])  # type: ignore

    def test_bundle_serialization(self):
        b = Bundle(id="b1", transactions=["0xa"], block_number=1)
        d = b.model_dump()
        assert d["id"] == "b1"
        assert d["block_number"] == 1
        assert d["min_timestamp"] is None


class TestBundleStatus:
    def test_pending_status(self):
        s = BundleStatus(bundle_id="b1", status="pending")
        assert s.status == "pending"
        assert s.profit is None

    def test_landed_status(self):
        s = BundleStatus(
            bundle_id="b1",
            status="landed",
            block_number=18_000_000,
            tx_hash="0xabc",
            profit="50000000000000000",
            gas_used=150_000,
        )
        assert s.block_number == 18_000_000
        assert s.gas_used == 150_000

    def test_failed_status(self):
        s = BundleStatus(
            bundle_id="b1", status="failed", error="simulation reverted"
        )
        assert s.error == "simulation reverted"


class TestAuction:
    def test_open_auction(self):
        a = Auction(
            block_number=18_000_000,
            bids=[
                AuctionBid(
                    bidder="0x1234",
                    amount="100000000000000000",
                    bundle_hash="0xhash",
                    timestamp=1700000000,
                )
            ],
            status="open",
            deadline=1700000012,
        )
        assert a.status == "open"
        assert len(a.bids) == 1
        assert a.winner is None

    def test_finalized_auction(self):
        a = Auction(
            block_number=18_000_000,
            bids=[],
            winner="0x5678",
            winning_bid="200000000000000000",
            status="finalized",
            deadline=1700000012,
        )
        assert a.winner == "0x5678"


class TestRelayStats:
    def test_active_relay(self):
        r = RelayStats(
            relay_id="relay-1",
            name="Flashbots",
            url="https://relay.flashbots.net",
            status="active",
            bundles_submitted=1000,
            bundles_landed=950,
            avg_latency_ms=45.2,
            success_rate=0.95,
            last_seen=1700000000,
        )
        assert r.success_rate == 0.95
        assert r.avg_latency_ms == 45.2


class TestMempoolSnapshot:
    def test_snapshot(self):
        m = MempoolSnapshot(
            size=5000,
            pending_txs=4800,
            gas_stats=GasStats(
                min="10000000000",
                max="100000000000",
                avg="30000000000",
                median="25000000000",
            ),
            top_tokens=[
                TokenCount(token="WETH", count=1200),
                TokenCount(token="USDC", count=800),
            ],
        )
        assert m.size == 5000
        assert len(m.top_tokens) == 2


class TestEngineHealth:
    def test_healthy(self):
        h = EngineHealth(
            status="healthy",
            uptime=86400,
            version="1.0.0",
            chain_id=1,
            block_number=18_000_000,
            peer_count=50,
            mempool_size=5000,
            bundle_count=100,
            active_relays=3,
            last_block_time=1700000000,
        )
        assert h.status == "healthy"
        assert h.chain_id == 1

    def test_defaults(self):
        h = EngineHealth(
            status="degraded",
            uptime=0,
            version="0.1.0",
            chain_id=5,
            block_number=0,
            peer_count=0,
            mempool_size=0,
            active_relays=0,
        )
        assert h.bundle_count == 0
        assert h.last_block_time == 0


class TestSimulationResult:
    def test_successful_simulation(self):
        s = SimulationResult(
            success=True,
            profit="50000000000000000",
            gas_used=150_000,
            effective_gas_price="30000000000",
            logs=["Transfer(from, to, 100)"],
            state_changes=[],
        )
        assert s.success is True
        assert s.error is None

    def test_failed_simulation(self):
        s = SimulationResult(
            success=False,
            profit="0",
            gas_used=0,
            effective_gas_price="0",
            logs=[],
            state_changes=[],
            error="execution reverted: insufficient balance",
        )
        assert s.success is False
        assert "insufficient balance" in s.error  # type: ignore


class TestProfitHistory:
    def test_profit_history(self):
        p = ProfitHistory(
            time_range="24h",
            total_profit="1000000000000000000",
            total_cost="200000000000000000",
            net_profit="800000000000000000",
            bundle_count=50,
            success_rate=0.92,
            by_strategy={"arbitrage": {"profit": "500000000000000000", "count": 30}},
            data_points=[
                {"timestamp": 1700000000, "profit": "100000000000000000"}
            ],
        )
        assert p.bundle_count == 50
        assert "arbitrage" in p.by_strategy


class TestOFAStats:
    def test_ofa_stats(self):
        o = OFAStats(
            txs_protected=10_000,
            sandwich_blocked=500,
            mev_captured="5000000000000000000",
            user_rebates="2500000000000000000",
            rebate_rate=0.5,
            avg_savings_per_tx="250000000000000",
        )
        assert o.rebate_rate == 0.5


class TestMEVEvent:
    def test_event(self):
        e = MEVEvent(
            type="bundle_landed",
            data={"bundle_id": "b1", "profit": "100"},
            timestamp=1700000000,
        )
        assert e.type == "bundle_landed"


class TestChatResponse:
    def test_simple_response(self):
        r = ChatResponse(
            message="MEV stands for Maximal Extractable Value.",
            conversation_id="conv-1",
        )
        assert r.tools_called is None

    def test_response_with_tools(self):
        r = ChatResponse(
            message="Here is the auction data.",
            conversation_id="conv-2",
            tools_called=[
                {"tool_name": "get_auction", "success": True, "result": {}}
            ],
        )
        assert len(r.tools_called) == 1  # type: ignore


class TestMEVRole:
    def test_roles(self):
        assert MEVRole.SEARCHER.value == "searcher"
        assert MEVRole.BUILDER.value == "builder"
        assert MEVRole.VALIDATOR.value == "validator"
        assert MEVRole.OPERATOR.value == "operator"
        assert MEVRole.ANALYST.value == "analyst"
