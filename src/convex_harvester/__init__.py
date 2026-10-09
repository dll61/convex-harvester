"""ConvexHarvester: High-Frequency Adaptive Profit Retention & Convex Trailing Harvester.

A mathematical, microsecond-to-sub-second execution framework designed to eliminate
the 'Profit-Giveback Syndrome' (浮盈回吐综合征) in high-frequency trading and crypto perpetuals.
"""

from .core import ConvexHarvester, PositionState, PositionSide, HarvesterConfig, HarvestActionType
from .retention_model import (
    calculate_convex_trailing_stop,
    RetentionModelConfig,
    ProfitRetentionMetrics,
)
from .exhaustion_detector import (
    TemporalExhaustionDetector,
    ExhaustionSignal,
)
from .microstructure import (
    OrderbookDepthAnalyzer,
    DepthImbalanceMetrics,
)

__version__ = "1.0.0"
__all__ = [
    "ConvexHarvester",
    "PositionState",
    "PositionSide",
    "HarvesterConfig",
    "HarvestActionType",
    "calculate_convex_trailing_stop",
    "RetentionModelConfig",
    "ProfitRetentionMetrics",
    "TemporalExhaustionDetector",
    "ExhaustionSignal",
    "OrderbookDepthAnalyzer",
    "DepthImbalanceMetrics",
]
