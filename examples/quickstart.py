"""Quickstart Demonstration of ConvexHarvester.

Run with:
    python examples/quickstart.py
"""

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from convex_harvester import (
    ConvexHarvester,
    PositionSide,
    HarvestActionType,
    HarvesterConfig,
)
from convex_harvester.connectors import MockExchangeConnector


def on_position_exit(pos, action):
    net_pnl = pos.current_pnl_pct - 0.060  # Deduct 0.060% round-trip friction
    print("\n" + "=" * 65)
    print(f"  🏁 POSITION HARVESTED: {pos.symbol} [{pos.side.value}]")
    print("=" * 65)
    print(f"  - Exit Trigger:   {action.value}")
    print(f"  - Entry Price:    ${pos.entry_price:.4f}")
    print(f"  - Exit Price:     ${pos.exit_price:.4f}")
    print(f"  - Max Float(MFE): {pos.highest_pnl_pct:+.3f}%")
    print(f"  - Gross PnL:      {pos.current_pnl_pct:+.3f}%")
    print(f"  - Net Realized:   {net_pnl:+.3f}% (After 0.060% fees)")
    print(f"  - Shield Status:  {'ACTIVE 🛡️' if pos.is_break_even_shield_active else 'OFF'}")
    print("=" * 65)


def main():
    print("=" * 65)
    print("  🚀 CONVEX HARVESTER REAL-TIME SIMULATION DEMO")
    print("=" * 65)

    # 1. Initialize Mock Connector and Harvester Engine
    connector = MockExchangeConnector(initial_price=100.00)
    harvester = ConvexHarvester(
        connector=connector,
        config=HarvesterConfig(),
        on_exit_callback=on_position_exit,
    )

    # 2. Track a new LONG position on BTC-PERP
    symbol = "BTC-PERP"
    entry_price = 100.00
    pos = harvester.track_position(
        symbol=symbol,
        side=PositionSide.LONG,
        size=1.0,
        entry_price=entry_price,
    )
    print(f"[ENTRY] Bought {symbol} at ${entry_price:.4f} | Initial Stop Loss: {pos.trailing_stop_pct:+.2f}%\n")

    # 3. Simulate sequential market ticks
    # Tick 1: Small rise to +0.050%
    # Tick 2: Breakout surge to +0.120% (Break-Even Shield Arms!)
    # Tick 3: Peak expansion to +0.320% (Convex Trailing Stop scales up!)
    # Tick 4: Stall at peak for 5 seconds (Peak Exhaustion trigger!)
    # Tick 5: Retracement hits trailing stop
    ticks = [
        (100.03, "Micro fluctuation (+0.030%)"),
        (100.07, "Momentum building (+0.070%)"),
        (100.11, "Surge hits +0.110% -> 🛡️ BREAK-EVEN SHIELD ACTIVATED!"),
        (100.22, "Impulse expands to +0.220% -> Convex trailing stop ratchet up"),
        (100.35, "Peak excursion reached (+0.350%)"),
        (100.31, "Micro-pullback from peak (+0.310%)"),
        (100.24, "Trailing stop triggered!"),
    ]

    for px, desc in ticks:
        time.sleep(0.3)
        action = harvester.update_tick(symbol, current_price=px)
        pnl = pos.current_pnl_pct
        stop = pos.trailing_stop_pct
        shield = "🛡️ ON" if pos.is_break_even_shield_active else "OFF"
        print(f"[TICK] Px: ${px:.2f} | PnL: {pnl:+.3f}% | Stop: {stop:+.3f}% | Shield: {shield:<5} | {desc}")

        if action != HarvestActionType.HOLD:
            break


if __name__ == "__main__":
    main()
