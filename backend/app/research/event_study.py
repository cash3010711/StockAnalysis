"""Event study statistical analysis of stock selection factors."""

from dataclasses import asdict, dataclass
import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.research.config import StudyConfig

STUDY_FACTORS: List[str] = [
    # 5 Strategies
    "strat_ma_pullback",
    "strat_breakout_20d",
    "strat_macd_cross",
    "strat_kd_cross",
    "strat_bb_breakout",
    # Fundamental & Chips
    "rev_yoy_pos",
    "debt_ok",
    "inst_net_pos",
    # New Factors
    "market_bull",
    "vcp",
    "trust_streak3",
    "inst_vol_ratio",
    "rev_accel",
    "rev_new_high",
    "rs_top20",
]


@dataclass
class FactorStat:
    """Statistical evaluation metrics for a single factor."""

    factor_name: str
    sample_count: int
    hit_count: int
    hit_rate: float
    base_hit_rate: float
    lift: float
    ci_lower: float
    ci_upper: float
    lift_lower: float
    lift_upper: float
    sample_insufficient: bool

    def to_dict(self) -> Dict:
        return asdict(self)


def calculate_wilson_ci(hits: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate Wilson score interval for a binomial proportion."""
    if total <= 0:
        return 0.0, 0.0
    # Standard normal z for two-sided confidence
    z = 1.95996 if abs(confidence - 0.95) < 0.01 else 1.96
    p = hits / total
    denom = 1.0 + (z**2) / total
    center = (p + (z**2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p * (1.0 - p)) / total + (z**2) / (4.0 * total**2))) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


def evaluate_factor_subset(
    df_subset: pd.DataFrame,
    factor_name: str,
    base_hit_rate: float,
    min_sample_size: int = 100,
) -> FactorStat:
    """Evaluate performance of a single factor in a filtered subset of samples."""
    if df_subset.empty or factor_name not in df_subset.columns:
        return FactorStat(
            factor_name=factor_name,
            sample_count=0,
            hit_count=0,
            hit_rate=0.0,
            base_hit_rate=base_hit_rate,
            lift=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            lift_lower=0.0,
            lift_upper=0.0,
            sample_insufficient=True,
        )

    triggered = df_subset[df_subset[factor_name] == True]
    n = len(triggered)
    hits = int(triggered["forward_hit"].sum())
    hit_rate = hits / n if n > 0 else 0.0
    lift = hit_rate / base_hit_rate if base_hit_rate > 0 else 0.0
    ci_lower, ci_upper = calculate_wilson_ci(hits, n)
    lift_lower = ci_lower / base_hit_rate if base_hit_rate > 0 else 0.0
    lift_upper = ci_upper / base_hit_rate if base_hit_rate > 0 else 0.0
    sample_insufficient = n < min_sample_size

    return FactorStat(
        factor_name=factor_name,
        sample_count=n,
        hit_count=hits,
        hit_rate=hit_rate,
        base_hit_rate=base_hit_rate,
        lift=lift,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        lift_lower=lift_lower,
        lift_upper=lift_upper,
        sample_insufficient=sample_insufficient,
    )


def split_panel_train_test(
    panel: pd.DataFrame,
    config: Optional[StudyConfig] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    """Split panel into train and test sets with purging of train tail.

    Returns:
        (train_df, test_df, purged_sample_count)
    """
    cfg = config or StudyConfig()

    # Filter to valid and non-hard-excluded samples only
    valid_panel = panel[
        (panel["forward_valid"] == True) & (panel["hard_exclude"] == False)
    ].copy()

    if valid_panel.empty:
        return pd.DataFrame(), pd.DataFrame(), 0

    all_dates = sorted(valid_panel["date"].unique().tolist())
    train_dates = [d for d in all_dates if d <= cfg.train_end]
    test_dates = [d for d in all_dates if d >= cfg.test_start]

    # Purge the last purge_days trading dates of train period
    if len(train_dates) > cfg.purge_days:
        effective_train_dates = set(train_dates[: -cfg.purge_days])
        purged_dates = set(train_dates[-cfg.purge_days :])
    else:
        effective_train_dates = set(train_dates)
        purged_dates = set()

    purged_count = int(valid_panel["date"].isin(purged_dates).sum())

    train_df = valid_panel[valid_panel["date"].isin(effective_train_dates)].copy()
    test_df = valid_panel[valid_panel["date"].isin(set(test_dates))].copy()

    return train_df, test_df, purged_count


def run_event_study(
    panel: pd.DataFrame,
    config: Optional[StudyConfig] = None,
) -> Dict:
    """Run full factor event study on panel data.

    Returns dictionary containing:
    - train_stats: Dict[str, FactorStat]
    - test_stats: Dict[str, FactorStat]
    - train_base_hit_rate: float
    - test_base_hit_rate: float
    - train_sample_count: int
    - test_sample_count: int
    - purged_sample_count: int
    - excluded_samples: Dict[str, int]
    """
    cfg = config or StudyConfig()
    train_df, test_df, purged_count = split_panel_train_test(panel, config=cfg)

    train_n = len(train_df)
    train_hits = int(train_df["forward_hit"].sum()) if train_n > 0 else 0
    train_base_rate = train_hits / train_n if train_n > 0 else 0.0

    test_n = len(test_df)
    test_hits = int(test_df["forward_hit"].sum()) if test_n > 0 else 0
    test_base_rate = test_hits / test_n if test_n > 0 else 0.0

    train_stats: Dict[str, FactorStat] = {}
    test_stats: Dict[str, FactorStat] = {}

    for factor in STUDY_FACTORS:
        train_stats[factor] = evaluate_factor_subset(
            train_df,
            factor,
            base_hit_rate=train_base_rate,
            min_sample_size=cfg.min_sample_size,
        )
        test_stats[factor] = evaluate_factor_subset(
            test_df,
            factor,
            base_hit_rate=test_base_rate,
            min_sample_size=cfg.min_sample_size,
        )

    # Count breakdown of exclusions
    hard_excluded = int(panel["hard_exclude"].sum())
    gap_excluded = int((panel["exclude_reason"] == "dividend_or_split_gap").sum())
    tail_excluded = int((panel["exclude_reason"] == "insufficient_future_data").sum())

    return {
        "train_stats": train_stats,
        "test_stats": test_stats,
        "train_base_hit_rate": train_base_rate,
        "test_base_hit_rate": test_base_rate,
        "train_sample_count": train_n,
        "test_sample_count": test_n,
        "purged_sample_count": purged_count,
        "excluded_samples": {
            "hard_exclude": hard_excluded,
            "dividend_or_split_gap": gap_excluded,
            "insufficient_future_data": tail_excluded,
            "purged": purged_count,
        },
        "train_df": train_df,
        "test_df": test_df,
    }
