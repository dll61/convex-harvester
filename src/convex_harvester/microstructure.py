"""L2 Orderbook Depth Imbalance & Microstructure Anti-Spoofing Analyzer.

Provides quantitative orderbook telemetry:
1. Multi-level Depth Imbalance Ratio (Bids vs. Asks).
2. Whale Spoofing & Order Count Concentration Analysis.
3. Sudden Liquidity Vacuum / Reverse Shift Alerts.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DepthImbalanceMetrics:
    """Quantitative orderbook metrics across top levels."""
    spread_pct: float
    bid_depth_usd: float
    ask_depth_usd: float
    imbalance_ratio: float
    best_bid_orders_count: int
    best_ask_orders_count: int
    is_spoofed_bid: bool
    is_spoofed_ask: bool


class OrderbookDepthAnalyzer:
    """Analyzes raw L2 book snapshots to detect adverse liquidity shifts."""

    @staticmethod
    def analyze_orderbook(
        bids: List[Dict[str, Any]],
        asks: List[Dict[str, Any]],
        depth_levels: int = 5,
        spoof_concentration_threshold: float = 0.85,
    ) -> Optional[DepthImbalanceMetrics]:
        """Calculates microstructure metrics from L2 bids and asks lists.

        Each level entry is expected to contain:
            {"px": float or str, "sz": float or str, "n": Optional[int]}
        """
        if not bids or not asks:
            return None

        best_bid = float(bids[0].get("px", 0.0))
        best_ask = float(asks[0].get("px", 0.0))
        mid_px = (best_bid + best_ask) / 2.0

        if mid_px <= 0:
            return None

        spread_pct = (best_ask - best_bid) / mid_px * 100.0

        top_bids = bids[:depth_levels]
        top_asks = asks[:depth_levels]

        bid_notionals = [float(b.get("px", 0.0)) * float(b.get("sz", 0.0)) for b in top_bids]
        ask_notionals = [float(a.get("px", 0.0)) * float(a.get("sz", 0.0)) for a in top_asks]

        total_bid_usd = sum(bid_notionals)
        total_ask_usd = sum(ask_notionals)

        imbalance_ratio = total_bid_usd / max(total_ask_usd, 0.01)

        # Order count on best bid/ask
        best_bid_n = int(bids[0].get("n", 1))
        best_ask_n = int(asks[0].get("n", 1))

        # Spoofing check: Top level concentration exceeds threshold and has only 1 order
        is_spoofed_bid = False
        if total_bid_usd > 0 and (bid_notionals[0] / total_bid_usd) >= spoof_concentration_threshold and best_bid_n == 1:
            is_spoofed_bid = True

        is_spoofed_ask = False
        if total_ask_usd > 0 and (ask_notionals[0] / total_ask_usd) >= spoof_concentration_threshold and best_ask_n == 1:
            is_spoofed_ask = True

        return DepthImbalanceMetrics(
            spread_pct=round(spread_pct, 4),
            bid_depth_usd=round(total_bid_usd, 2),
            ask_depth_usd=round(total_ask_usd, 2),
            imbalance_ratio=round(imbalance_ratio, 2),
            best_bid_orders_count=best_bid_n,
            best_ask_orders_count=best_ask_n,
            is_spoofed_bid=is_spoofed_bid,
            is_spoofed_ask=is_spoofed_ask,
        )
