"""Core Harvester Orchestrator.

Combines Convex Retention, Temporal Exhaustion Detection, and Microstructure Telemetry
into an autonomous sub-second execution loop.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .connectors.base import BaseExchangeConnector
from .exhaustion_detector import ExhaustionReason, TemporalExhaustionDetector
from .microstructure import OrderbookDepthAnalyzer
from .retention_model import RetentionModelConfig, calculate_convex_trailing_stop


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class HarvestActionType(str, Enum):
    HOLD = "HOLD"
    CONVEX_TRAILING_EXIT = "CONVEX_TRAILING_EXIT"
    PEAK_EXHAUSTION_EXIT = "PEAK_EXHAUSTION_EXIT"
    LIQUIDITY_REVERSAL_EXIT = "LIQUIDITY_REVERSAL_EXIT"
    HARD_STOP_EXIT = "HARD_STOP_EXIT"


@dataclass
class PositionState:
    """State tracking for an active position under Harvester protection."""
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    entry_time: float = field(default_factory=time.time)

    # Dynamic metrics
    current_price: float = 0.0
    current_pnl_pct: float = 0.0
    highest_pnl_pct: float = 0.0
    lowest_pnl_pct: float = 0.0
    trailing_stop_pct: float = -0.38

    # Protection flags
    is_break_even_shield_active: bool = False
    is_closed: bool = False
    close_reason: HarvestActionType = HarvestActionType.HOLD
    exit_price: Optional[float] = None


@dataclass
class HarvesterConfig:
    """Master configuration for ConvexHarvester engine."""
    retention: RetentionModelConfig = field(default_factory=RetentionModelConfig)
    enable_temporal_exhaustion: bool = True
    enable_microstructure_check: bool = True
    poll_interval_seconds: float = 0.5


class ConvexHarvester:
    """Autonomous Real-time Position Harvester Engine."""

    def __init__(
        self,
        connector: BaseExchangeConnector,
        config: HarvesterConfig = HarvesterConfig(),
        on_exit_callback: Optional[Callable[[PositionState, HarvestActionType], None]] = None,
    ):
        self.connector = connector
        self.config = config
        self.on_exit_callback = on_exit_callback
        self.positions: Dict[str, PositionState] = {}
        self.exhaustion_detectors: Dict[str, TemporalExhaustionDetector] = {}

    def track_position(
        self,
        symbol: str,
        side: PositionSide,
        size: float,
        entry_price: float,
    ) -> PositionState:
        """Registers a new position to be actively guarded."""
        pos = PositionState(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            trailing_stop_pct=-abs(self.config.retention.initial_hard_stop_loss_pct),
        )
        self.positions[symbol] = pos
        self.exhaustion_detectors[symbol] = TemporalExhaustionDetector(
            min_pnl_to_arm_pct=self.config.retention.break_even_activation_mfe,
            peak_stall_seconds=4.5,
            peak_pullback_threshold_pct=0.025,
            prolonged_plateau_seconds=12.0,
        )
        return pos

    def update_tick(self, symbol: str, current_price: Optional[float] = None) -> HarvestActionType:
        """Evaluates a single price tick against all protection algorithms."""
        pos = self.positions.get(symbol)
        if not pos or pos.is_closed:
            return HarvestActionType.HOLD

        # Fetch current price if not provided
        px = current_price if current_price is not None else self.connector.get_mid_price(symbol)
        pos.current_price = px

        # Calculate floating PnL %
        if pos.side == PositionSide.LONG:
            pnl_pct = (px - pos.entry_price) / pos.entry_price * 100.0
        else:
            pnl_pct = (pos.entry_price - px) / pos.entry_price * 100.0

        pos.current_pnl_pct = round(pnl_pct, 4)
        pos.highest_pnl_pct = max(pos.highest_pnl_pct, pos.current_pnl_pct)
        pos.lowest_pnl_pct = min(pos.lowest_pnl_pct, pos.current_pnl_pct)

        # 1. Update Convex Trailing Model
        new_stop, shield_active = calculate_convex_trailing_stop(
            mfe_pct=pos.highest_pnl_pct,
            current_pnl_pct=pos.current_pnl_pct,
            config=self.config.retention,
        )
        pos.trailing_stop_pct = max(pos.trailing_stop_pct, new_stop)
        pos.is_break_even_shield_active = shield_active

        # Check Hard Stop Loss or Trailing Stop Breach
        if pos.current_pnl_pct <= pos.trailing_stop_pct:
            action = (
                HarvestActionType.CONVEX_TRAILING_EXIT
                if pos.is_break_even_shield_active
                else HarvestActionType.HARD_STOP_EXIT
            )
            return self._execute_exit(pos, action)

        # 2. Check Temporal Peak Exhaustion
        if self.config.enable_temporal_exhaustion:
            detector = self.exhaustion_detectors.get(symbol)
            if detector:
                sig = detector.update(pos.current_pnl_pct)
                if sig.is_exhausted:
                    return self._execute_exit(pos, HarvestActionType.PEAK_EXHAUSTION_EXIT)

        # 3. Check Orderbook Microstructure Liquidity Shift
        if self.config.enable_microstructure_check:
            try:
                bids, asks = self.connector.get_orderbook(symbol)
                metrics = OrderbookDepthAnalyzer.analyze_orderbook(bids, asks)
                if metrics:
                    # If LONG and buyer support dissolves (Imbalance < 0.70x or spoofed bid)
                    if pos.side == PositionSide.LONG and (metrics.imbalance_ratio < 0.70 or metrics.is_spoofed_bid):
                        if pos.current_pnl_pct >= self.config.retention.break_even_stop_floor:
                            return self._execute_exit(pos, HarvestActionType.LIQUIDITY_REVERSAL_EXIT)
                    # If SHORT and seller wall collapses (Imbalance > 1.45x)
                    elif pos.side == PositionSide.SHORT and metrics.imbalance_ratio > 1.45:
                        if pos.current_pnl_pct >= self.config.retention.break_even_stop_floor:
                            return self._execute_exit(pos, HarvestActionType.LIQUIDITY_REVERSAL_EXIT)
            except Exception:
                pass

        return HarvestActionType.HOLD

    def _execute_exit(self, pos: PositionState, action: HarvestActionType) -> HarvestActionType:
        """Executes position exit order and marks position closed."""
        pos.is_closed = True
        pos.close_reason = action
        pos.exit_price = pos.current_price

        # Close position via connector
        close_side = "SELL" if pos.side == PositionSide.LONG else "BUY"
        self.connector.close_position(
            symbol=pos.symbol,
            side=close_side,
            size=pos.size,
            reduce_only=True,
        )

        if self.on_exit_callback:
            try:
                self.on_exit_callback(pos, action)
            except Exception:
                pass

        return action
