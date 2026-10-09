"""Temporal Peak Exhaustion & Velocity Decay Detector.

Monitors tick-by-tick time series to detect momentum stalls at local peaks.
Triggers proactive cash-outs before adverse market maker sweeps erase accumulated gains.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ExhaustionReason(str, Enum):
    """Classification tag for momentum exhaustion."""
    NONE = "NONE"
    PEAK_STALL_MICRO_PULLBACK = "PEAK_STALL_MICRO_PULLBACK"
    PROLONGED_HIGH_PLATEAU = "PROLONGED_HIGH_PLATEAU"
    VOLATILITY_COLLAPSE = "VOLATILITY_COLLAPSE"


@dataclass
class ExhaustionSignal:
    """Detection result emitted by the exhaustion detector."""
    is_exhausted: bool
    reason: ExhaustionReason
    stagnation_seconds: float
    retrace_from_peak_pct: float
    peak_pnl_pct: float


class TemporalExhaustionDetector:
    """Detects when an active position's momentum has stalled at a peak.

    Empirical Rationale:
    --------------------
    In crypto perpetuals and ultra-short scalping, local price spikes (MFE) typically
    exhaust within 3 to 8 seconds. Waiting for a conventional 0.20% trailing retracement
    often results in giving back 60-80% of peak gains due to orderbook air-pockets.

    By tracking the time elapsed since the last MFE update (tau = t - t_peak) and the
    micro-pullback from peak, this detector locks in gains at the exact inflection point.
    """

    def __init__(
        self,
        min_pnl_to_arm_pct: float = 0.095,
        peak_stall_seconds: float = 4.5,
        peak_pullback_threshold_pct: float = 0.025,
        prolonged_plateau_seconds: float = 12.0,
    ):
        self.min_pnl_to_arm_pct = min_pnl_to_arm_pct
        self.peak_stall_seconds = peak_stall_seconds
        self.peak_pullback_threshold_pct = peak_pullback_threshold_pct
        self.prolonged_plateau_seconds = prolonged_plateau_seconds

        self.highest_pnl_pct: float = 0.0
        self.time_of_highest_pnl: float = time.time()
        self.entry_time: float = time.time()

    def reset(self, entry_time: Optional[float] = None) -> None:
        """Resets the detector for a new position."""
        now = entry_time or time.time()
        self.highest_pnl_pct = 0.0
        self.time_of_highest_pnl = now
        self.entry_time = now

    def update(self, current_pnl_pct: float, timestamp: Optional[float] = None) -> ExhaustionSignal:
        """Evaluates the latest tick PnL against time and peak thresholds."""
        now = timestamp or time.time()

        # Update peak if current PnL exceeds historical peak
        if current_pnl_pct > self.highest_pnl_pct:
            self.highest_pnl_pct = current_pnl_pct
            self.time_of_highest_pnl = now

        stagnation_sec = max(0.0, now - self.time_of_highest_pnl)
        retrace_pct = max(0.0, self.highest_pnl_pct - current_pnl_pct)

        # Detector only arms when the position has achieved minimum viability threshold
        if self.highest_pnl_pct < self.min_pnl_to_arm_pct:
            return ExhaustionSignal(
                is_exhausted=False,
                reason=ExhaustionReason.NONE,
                stagnation_seconds=stagnation_sec,
                retrace_from_peak_pct=retrace_pct,
                peak_pnl_pct=self.highest_pnl_pct,
            )

        # Condition 1: 4.5s Peak Stall with Micro-Pullback
        if stagnation_sec >= self.peak_stall_seconds and retrace_pct >= self.peak_pullback_threshold_pct:
            return ExhaustionSignal(
                is_exhausted=True,
                reason=ExhaustionReason.PEAK_STALL_MICRO_PULLBACK,
                stagnation_seconds=stagnation_sec,
                retrace_from_peak_pct=retrace_pct,
                peak_pnl_pct=self.highest_pnl_pct,
            )

        # Condition 2: Prolonged High Plateau (Holding near peak for >= 12s without breakout)
        if stagnation_sec >= self.prolonged_plateau_seconds:
            return ExhaustionSignal(
                is_exhausted=True,
                reason=ExhaustionReason.PROLONGED_HIGH_PLATEAU,
                stagnation_seconds=stagnation_sec,
                retrace_from_peak_pct=retrace_pct,
                peak_pnl_pct=self.highest_pnl_pct,
            )

        return ExhaustionSignal(
            is_exhausted=False,
            reason=ExhaustionReason.NONE,
            stagnation_seconds=stagnation_sec,
            retrace_from_peak_pct=retrace_pct,
            peak_pnl_pct=self.highest_pnl_pct,
        )
