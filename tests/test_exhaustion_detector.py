import pytest
from convex_harvester.exhaustion_detector import (
    TemporalExhaustionDetector,
    ExhaustionReason,
)


def test_detector_not_armed_below_minimum_mfe():
    """Verify detector does not trigger when MFE is below activation threshold."""
    detector = TemporalExhaustionDetector(min_pnl_to_arm_pct=0.095)
    detector.reset(entry_time=1000.0)

    # 10 seconds pass at +0.050%
    sig = detector.update(current_pnl_pct=0.050, timestamp=1010.0)
    assert not sig.is_exhausted
    assert sig.reason == ExhaustionReason.NONE


def test_peak_stall_micro_pullback_trigger():
    """Verify 4.5s stall with micro-pullback triggers exhaustion exit."""
    detector = TemporalExhaustionDetector(
        min_pnl_to_arm_pct=0.095,
        peak_stall_seconds=4.5,
        peak_pullback_threshold_pct=0.025,
    )
    detector.reset(entry_time=1000.0)

    # Reaches peak of +0.200% at t=1002.0
    detector.update(current_pnl_pct=0.200, timestamp=1002.0)

    # At t=1004.0 (2s elapsed), pulls back to +0.170% -> Not yet 4.5s
    sig1 = detector.update(current_pnl_pct=0.170, timestamp=1004.0)
    assert not sig1.is_exhausted

    # At t=1007.0 (5s elapsed from peak), pulls back to +0.170% (retrace 0.030% >= 0.025%)
    sig2 = detector.update(current_pnl_pct=0.170, timestamp=1007.0)
    assert sig2.is_exhausted
    assert sig2.reason == ExhaustionReason.PEAK_STALL_MICRO_PULLBACK


def test_prolonged_plateau_trigger():
    """Verify holding near peak for 12s without new high triggers plateau exit."""
    detector = TemporalExhaustionDetector(
        min_pnl_to_arm_pct=0.095,
        prolonged_plateau_seconds=12.0,
    )
    detector.reset(entry_time=1000.0)

    # Peak +0.150% at t=1001.0
    detector.update(current_pnl_pct=0.150, timestamp=1001.0)

    # 13s pass, price still at +0.145% (retrace only 0.005%, but 13s > 12s)
    sig = detector.update(current_pnl_pct=0.145, timestamp=1014.0)
    assert sig.is_exhausted
    assert sig.reason == ExhaustionReason.PROLONGED_HIGH_PLATEAU
