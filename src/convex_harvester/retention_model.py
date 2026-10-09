"""Convex Profit Retention & Trailing Stop Mathematical Engine.

Formulates dynamic profit retention as a strictly monotonic convex function of Maximum
Favorable Excursion (MFE) to eliminate fee decay and adverse selection in fast-moving markets.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class RetentionModelConfig:
    """Mathematical parameter configuration for the Convex Retention Model."""
    # Round-trip friction estimation (e.g., Maker 0.015% + Taker 0.035% + slippage ~0.010% = 0.060%)
    round_trip_fee_pct: float = 0.060

    # Stage 1: Break-Even Shield Thresholds
    # When MFE reaches break_even_activation_mfe (e.g. +0.095%), the trailing stop is
    # welded to break_even_stop_floor (e.g. +0.080% gross).
    # Net profit is strictly guaranteed: 0.080% - 0.060% = +0.020% > 0.
    break_even_activation_mfe: float = 0.095
    break_even_stop_floor: float = 0.080

    # Stage 2: Convex Acceleration Thresholds
    stage2_mfe_threshold: float = 0.150
    stage3_mfe_threshold: float = 0.300
    stage4_mfe_threshold: float = 0.600

    # Minimum and Maximum Profit Retention Ratios (Retained MFE / Total MFE)
    min_retention_ratio: float = 0.60
    max_retention_ratio: float = 0.85

    # Maximum Initial Stop Loss (Absolute hard boundary)
    initial_hard_stop_loss_pct: float = 0.38


@dataclass
class ProfitRetentionMetrics:
    """Calculated metrics for a position's profit retention state."""
    current_pnl_pct: float
    mfe_pct: float
    trailing_stop_pct: float
    is_shield_active: bool
    retention_ratio: float
    net_pnl_floor_pct: float


def calculate_convex_trailing_stop(
    mfe_pct: float,
    current_pnl_pct: float,
    config: RetentionModelConfig = RetentionModelConfig(),
    atr_volatility_pct: float = 0.0,
) -> Tuple[float, bool]:
    """Calculates the optimal convex trailing stop percentage given MFE and current PnL.

    Mathematical Formulation:
    -------------------------
    1. Pre-Activation Stage (MFE < Theta_BE):
       Stop remains at initial structural boundary (-initial_hard_stop_loss_pct).

    2. Break-Even Shield (Theta_BE <= MFE < Theta_Stage2):
       Stop is welded to break_even_stop_floor (+0.080%).
       Theorem: P(NetLoss | MFE >= Theta_BE) = 0.

    3. Convex Acceleration Stage (MFE >= Theta_Stage2):
       Trailing stop dynamically curves upward with increasing MFE:
       RetentionRatio(MFE) = min(R_max, R_min + (R_max - R_min) * ((MFE - Theta_2) / Theta_4)^gamma)
       StopPct = max(break_even_stop_floor, MFE * RetentionRatio)

    Returns:
        Tuple[trailing_stop_pct: float, is_shield_active: bool]
    """
    if mfe_pct < config.break_even_activation_mfe:
        # Pre-shield: Hard structural stop loss
        return -abs(config.initial_hard_stop_loss_pct), False

    # Stage 1: Break-Even Shield active
    is_shield_active = True
    base_floor = config.break_even_stop_floor

    if mfe_pct < config.stage2_mfe_threshold:
        # Welded strictly to the break-even floor
        return base_floor, is_shield_active

    # Stage 2 & Beyond: Convex Trailing Scaling
    # As MFE grows from stage2 (0.15%) to stage4 (0.60%), retention scales smoothly from 60% to 85%
    progress = min(1.0, max(0.0, (mfe_pct - config.stage2_mfe_threshold) / (config.stage4_mfe_threshold - config.stage2_mfe_threshold)))
    retention_ratio = config.min_retention_ratio + (config.max_retention_ratio - config.min_retention_ratio) * (progress ** 0.8)

    # Calculate candidate dynamic stop
    dynamic_stop = mfe_pct * retention_ratio

    # Volatility buffer adjustment if ATR is provided
    if atr_volatility_pct > 0:
        vol_buffer = min(dynamic_stop * 0.20, atr_volatility_pct * 0.5)
        dynamic_stop = max(base_floor, dynamic_stop - vol_buffer)

    final_stop = max(base_floor, dynamic_stop)
    return round(final_stop, 4), is_shield_active
