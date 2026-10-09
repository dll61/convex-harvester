import pytest
from convex_harvester.retention_model import (
    calculate_convex_trailing_stop,
    RetentionModelConfig,
)


def test_pre_activation_hard_stop():
    """Verify stop remains at hard stop loss when MFE is below activation threshold."""
    config = RetentionModelConfig(initial_hard_stop_loss_pct=0.38, break_even_activation_mfe=0.095)
    stop, shield = calculate_convex_trailing_stop(mfe_pct=0.050, current_pnl_pct=0.040, config=config)
    assert stop == -0.38
    assert not shield


def test_break_even_shield_welded_floor():
    """Verify stop is welded to break-even floor once MFE touches activation threshold."""
    config = RetentionModelConfig(break_even_activation_mfe=0.095, break_even_stop_floor=0.080)
    stop, shield = calculate_convex_trailing_stop(mfe_pct=0.100, current_pnl_pct=0.090, config=config)
    assert stop == 0.080
    assert shield


def test_convex_acceleration_scaling():
    """Verify stop curves upward as MFE expands beyond stage 2 (0.150%)."""
    config = RetentionModelConfig()
    stop_stage1, _ = calculate_convex_trailing_stop(mfe_pct=0.120, current_pnl_pct=0.120, config=config)
    stop_stage2, _ = calculate_convex_trailing_stop(mfe_pct=0.250, current_pnl_pct=0.250, config=config)
    stop_stage3, _ = calculate_convex_trailing_stop(mfe_pct=0.500, current_pnl_pct=0.500, config=config)

    assert stop_stage1 == 0.080
    assert stop_stage2 > stop_stage1
    assert stop_stage3 > stop_stage2
    # At 0.500% MFE, trailing stop should retain majority of gains
    assert stop_stage3 >= 0.350


def test_net_green_mathematical_theorem():
    """Verify that whenever shield is active, net PnL floor after fees is strictly positive."""
    config = RetentionModelConfig(round_trip_fee_pct=0.060, break_even_stop_floor=0.080)
    for mfe in [0.095, 0.120, 0.200, 0.400, 1.000]:
        stop, shield = calculate_convex_trailing_stop(mfe_pct=mfe, current_pnl_pct=mfe, config=config)
        assert shield
        net_floor = stop - config.round_trip_fee_pct
        assert net_floor >= 0.020, f"Net floor must be >= +0.020%, got {net_floor} for MFE {mfe}"
