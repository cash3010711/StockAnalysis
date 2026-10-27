"""Configuration and parameters for factor event study."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class StudyConfig:
    """Parameters and thresholds for stock factor event study."""

    # Time split and purge
    train_end: str = "2024-12-31"
    test_start: str = "2025-01-01"
    purge_days: int = 20

    # Forward label definitions
    forward_window: int = 20
    target_gain: float = 0.15  # +15%
    stop_loss: float = 0.07    # -7%
    gap_threshold: float = 0.105  # 10.5% overnight gap (stock dividend / split filter)

    # Statistical thresholds
    min_sample_size: int = 100  # Minimum trigger samples in train set for valid weight
    wilson_confidence: float = 0.95
    top_quantile: float = 0.10  # Top 10% for evaluation
    target_lift: float = 2.0    # Success criterion: top 10% lift >= 2.0

    # Risk control hard filter thresholds
    eps_sum_min: float = 0.0
    margin_inc_max: float = 0.20

    # Factor thresholds (D4)
    market_ma_window: int = 60
    market_ma_slope_window: int = 20

    rs_return_window: int = 120
    rs_percentile_min: float = 0.80

    vcp_atr_ratio_lookback: int = 60
    vcp_atr_ratio_decay: float = 0.70
    vcp_vol_fast: int = 5
    vcp_vol_slow: int = 50
    vcp_high_lookback: int = 250
    vcp_high_pct: float = 0.85

    rev_accel_fast_months: int = 3
    rev_accel_slow_months: int = 12
    rev_new_high_lookback_months: int = 24

    trust_streak_days: int = 3
    inst_vol_ratio_days: int = 10
    inst_vol_ratio_min: float = 0.05
    debt_ratio_max: float = 60.0
