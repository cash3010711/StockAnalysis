"""Multi-factor scoring, normalization, and validation engine."""

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.research.config import StudyConfig
from app.research.event_study import FactorStat, STUDY_FACTORS


@dataclass
class DecileStat:
    """Statistics for a decile bin."""

    decile: int  # 1 to 10 (1 is top 10%, 10 is bottom 10%)
    sample_count: int
    hit_count: int
    hit_rate: float
    lift: float
    min_score: float
    max_score: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ValidationResult:
    """Summary of factor study scoring and out-of-sample validation."""

    passed: bool
    target_lift: float
    top10_lift: float
    top10_hit_rate: float
    test_base_hit_rate: float
    top10_sample_count: int
    test_sample_count: int
    train_sample_count: int
    weights: Dict[str, float]
    norm_q01: float
    norm_q99: float
    decile_stats: List[DecileStat]

    def to_dict(self) -> Dict:
        res = asdict(self)
        res["decile_stats"] = [d.to_dict() for d in self.decile_stats]
        return res


def fit_weights(
    train_stats: Dict[str, FactorStat],
    config: Optional[StudyConfig] = None,
) -> Dict[str, float]:
    """Fit factor weights strictly using training period metrics.

    Rule:
    weight = log(lift) if lift > 1.0 and not sample_insufficient else 0.0
    """
    weights: Dict[str, float] = {}
    for factor_name, stat in train_stats.items():
        if stat.sample_insufficient or stat.lift <= 1.0 or np.isnan(stat.lift):
            weights[factor_name] = 0.0
        else:
            weights[factor_name] = float(np.log(stat.lift))
    return weights


def calculate_raw_scores(
    df: pd.DataFrame,
    weights: Dict[str, float],
) -> pd.Series:
    """Calculate raw additive score for each row in df based on active factors."""
    if df.empty:
        return pd.Series(dtype=float)

    raw = np.zeros(len(df), dtype=float)
    for factor_name, weight in weights.items():
        if weight > 0.0 and factor_name in df.columns:
            active = df[factor_name].fillna(False).to_numpy(dtype=bool)
            raw += active.astype(float) * weight
    return pd.Series(raw, index=df.index, dtype=float)


def fit_normalization_params(
    train_raw_scores: pd.Series,
) -> Tuple[float, float]:
    """Fit 1st and 99th percentile bounds on training raw scores."""
    if train_raw_scores.empty:
        return 0.0, 1.0
    q01 = float(np.percentile(train_raw_scores, 1.0))
    q99 = float(np.percentile(train_raw_scores, 99.0))
    if q99 <= q01:
        q99 = q01 + 1e-4
    return q01, q99


def normalize_scores(
    raw_scores: pd.Series,
    q01: float,
    q99: float,
) -> pd.Series:
    """Scale raw scores linearly to [0, 100] clipped at bounds."""
    if raw_scores.empty:
        return pd.Series(dtype=float)
    norm = (raw_scores - q01) / (q99 - q01) * 100.0
    return pd.Series(np.clip(norm, 0.0, 100.0), index=raw_scores.index, dtype=float)


def compute_decile_table(
    df: pd.DataFrame,
    score_col: str = "score",
    hit_col: str = "forward_hit",
    base_hit_rate: Optional[float] = None,
) -> List[DecileStat]:
    """Divide scored dataset into 10 deciles (decile 1 = top 10% highest score)."""
    if df.empty:
        return []

    base_rate = base_hit_rate if base_hit_rate is not None else float(df[hit_col].mean())
    df_sorted = df.sort_values(score_col, ascending=False).reset_index(drop=True)
    n = len(df_sorted)

    deciles: List[DecileStat] = []
    # Use quantile bins
    for d in range(1, 11):
        start_idx = int(round((d - 1) * n / 10.0))
        end_idx = int(round(d * n / 10.0))
        bin_df = df_sorted.iloc[start_idx:end_idx]
        bin_n = len(bin_df)
        bin_hits = int(bin_df[hit_col].sum()) if bin_n > 0 else 0
        bin_rate = bin_hits / bin_n if bin_n > 0 else 0.0
        bin_lift = bin_rate / base_rate if base_rate > 0 else 0.0
        min_s = float(bin_df[score_col].min()) if bin_n > 0 else 0.0
        max_s = float(bin_df[score_col].max()) if bin_n > 0 else 0.0

        deciles.append(
            DecileStat(
                decile=d,
                sample_count=bin_n,
                hit_count=bin_hits,
                hit_rate=bin_rate,
                lift=bin_lift,
                min_score=min_s,
                max_score=max_s,
            )
        )
    return deciles


def evaluate_scoring_system(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    train_stats: Dict[str, FactorStat],
    config: Optional[StudyConfig] = None,
) -> ValidationResult:
    """Fit scoring parameters on train_df and evaluate out-of-sample on test_df."""
    cfg = config or StudyConfig()

    # 1. Fit weights from train stats
    weights = fit_weights(train_stats, config=cfg)

    # 2. Compute train raw scores and fit normalization params
    train_raw = calculate_raw_scores(train_df, weights)
    q01, q99 = fit_normalization_params(train_raw)

    # 3. Score test set using frozen train params
    test_raw = calculate_raw_scores(test_df, weights)
    test_df_scored = test_df.copy()
    test_df_scored["score"] = normalize_scores(test_raw, q01, q99)

    test_n = len(test_df_scored)
    test_hits = int(test_df_scored["forward_hit"].sum()) if test_n > 0 else 0
    test_base_rate = test_hits / test_n if test_n > 0 else 0.0

    # 4. Deciles
    deciles = compute_decile_table(
        test_df_scored,
        score_col="score",
        hit_col="forward_hit",
        base_hit_rate=test_base_rate,
    )

    # 5. Top 10% stats (decile 1)
    if deciles:
        top10_stat = deciles[0]
        top10_lift = top10_stat.lift
        top10_hit_rate = top10_stat.hit_rate
        top10_n = top10_stat.sample_count
    else:
        top10_lift = 0.0
        top10_hit_rate = 0.0
        top10_n = 0

    passed = bool(top10_lift >= cfg.target_lift)

    return ValidationResult(
        passed=passed,
        target_lift=cfg.target_lift,
        top10_lift=top10_lift,
        top10_hit_rate=top10_hit_rate,
        test_base_hit_rate=test_base_rate,
        top10_sample_count=top10_n,
        test_sample_count=test_n,
        train_sample_count=len(train_df),
        weights=weights,
        norm_q01=q01,
        norm_q99=q99,
        decile_stats=deciles,
    )
