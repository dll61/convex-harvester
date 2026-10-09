import pytest
from convex_harvester import (
    ConvexHarvester,
    PositionSide,
    HarvestActionType,
    HarvesterConfig,
)
from convex_harvester.connectors import MockExchangeConnector


def test_hard_stop_loss_lifecycle():
    """Verify position exits via HARD_STOP_EXIT when price dumps below -0.38% without seeing profit."""
    connector = MockExchangeConnector(initial_price=100.0)
    harvester = ConvexHarvester(connector=connector)

    pos = harvester.track_position(
        symbol="ETH-PERP",
        side=PositionSide.LONG,
        size=10.0,
        entry_price=100.0,
    )

    action = harvester.update_tick("ETH-PERP", current_price=99.60)  # -0.40% <= -0.38%
    assert action == HarvestActionType.HARD_STOP_EXIT
    assert pos.is_closed
    assert len(connector.closed_orders) == 1
    assert connector.closed_orders[0]["side"] == "SELL"


def test_convex_trailing_stop_lifecycle():
    """Verify position exits via CONVEX_TRAILING_EXIT after activating Break-Even Shield."""
    connector = MockExchangeConnector(initial_price=100.0)
    harvester = ConvexHarvester(connector=connector)

    pos = harvester.track_position(
        symbol="SOL-PERP",
        side=PositionSide.LONG,
        size=5.0,
        entry_price=100.0,
    )

    # 1. Price surges to +0.30%
    harvester.update_tick("SOL-PERP", current_price=100.30)
    assert pos.highest_pnl_pct == 0.30
    assert pos.is_break_even_shield_active
    assert pos.trailing_stop_pct > 0.15

    # 2. Price retraces below trailing stop
    action = harvester.update_tick("SOL-PERP", current_price=100.10)
    assert action == HarvestActionType.CONVEX_TRAILING_EXIT
    assert pos.is_closed
    assert pos.exit_price == 100.10


def test_liquidity_reversal_exit():
    """Verify position exits early if orderbook depth imbalance collapses."""
    connector = MockExchangeConnector(initial_price=100.0)
    harvester = ConvexHarvester(connector=connector)

    pos = harvester.track_position(
        symbol="AVAX-PERP",
        side=PositionSide.LONG,
        size=2.0,
        entry_price=100.0,
    )

    # Float is +0.090% (>= break_even_stop_floor 0.080%)
    harvester.update_tick("AVAX-PERP", current_price=100.09)

    # Orderbook buyer depth collapses: Bids $100 vs Asks $5000 -> Imbalance 0.02x < 0.70x
    connector.set_orderbook(
        bids=[{"px": 100.08, "sz": 1.0, "n": 1}],
        asks=[{"px": 100.10, "sz": 50.0, "n": 5}],
    )

    action = harvester.update_tick("AVAX-PERP", current_price=100.09)
    assert action == HarvestActionType.LIQUIDITY_REVERSAL_EXIT
    assert pos.is_closed
