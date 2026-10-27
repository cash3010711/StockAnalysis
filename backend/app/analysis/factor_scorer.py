"""Empirical multi-factor scoring and decile evaluation module for Taiwan stock scanner."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from app.analysis.indicators import compute_all_indicators
from app.analysis.layers import (
    compute_revenue_yoy,
    evaluate_chips_series,
    evaluate_fundamentals_series,
)
from app.analysis.strategies import evaluate_all_strategies
from app.research.factors import compute_revenue_factors

# Empirical weights fitted from 5-year event study (Train 2021-10 to 2024-12)
FROZEN_FACTOR_WEIGHTS: Dict[str, float] = {
    "rs_top20": 0.711,
    "strat_breakout_20d": 0.393,
    "strat_bb_breakout": 0.390,
    "rev_new_high": 0.293,
    "rev_accel": 0.259,
    "rev_yoy_pos": 0.196,
    "inst_net_pos": 0.139,
    "inst_vol_ratio": 0.084,
    "market_bull": 0.059,
    # Zero or negative lift factors
    "strat_ma_pullback": 0.0,
    "strat_macd_cross": 0.0,
    "strat_kd_cross": 0.0,
    "debt_ok": 0.0,
    "vcp": 0.0,
    "trust_streak3": 0.0,
}

# Empirical normalization bounds
NORM_Q01: float = 0.0
NORM_Q99: float = 1.95

FACTOR_DISPLAY_NAMES: Dict[str, str] = {
    "rs_top20": "相對強度RS前20%",
    "strat_breakout_20d": "帶量突破20日新高",
    "strat_bb_breakout": "布林通道壓縮突破",
    "rev_new_high": "月營收創24個月新高",
    "rev_accel": "月營收成長加速",
    "rev_yoy_pos": "月營收年增率>0%",
    "inst_net_pos": "外資投信10日買超>0",
    "inst_vol_ratio": "法人10日買超佔均量≥5%",
    "market_bull": "大盤多頭排列",
}

# Decile benchmark stats (empirical test out-of-sample)
DECILE_BENCHMARKS = [
    {"decile": 1, "min_score": 76.7, "hit_rate": 24.9, "lift": 2.00},
    {"decile": 2, "min_score": 56.9, "hit_rate": 19.7, "lift": 1.58},
    {"decile": 3, "min_score": 42.4, "hit_rate": 13.7, "lift": 1.10},
    {"decile": 4, "min_score": 32.2, "hit_rate": 11.1, "lift": 0.89},
    {"decile": 5, "min_score": 28.5, "hit_rate": 10.3, "lift": 0.82},
    {"decile": 6, "min_score": 19.9, "hit_rate": 9.2, "lift": 0.74},
    {"decile": 7, "min_score": 16.0, "hit_rate": 7.8, "lift": 0.62},
    {"decile": 8, "min_score": 12.3, "hit_rate": 9.1, "lift": 0.73},
    {"decile": 9, "min_score": 3.7, "hit_rate": 9.0, "lift": 0.72},
    {"decile": 10, "min_score": 0.0, "hit_rate": 9.9, "lift": 0.80},
]


@dataclass
class FactorScoreResult:
    """Factor score evaluation result for a stock."""

    factor_score: float
    factor_decile: int
    historical_hit_rate: float
    historical_lift: float
    triggered_factors: List[str] = field(default_factory=list)
    raw_score: float = 0.0


def score_to_decile(score: float) -> tuple[int, float, float]:
    """Map a 0-100 factor score to its empirical decile, hit rate, and lift."""
    for b in DECILE_BENCHMARKS:
        if score >= b["min_score"]:
            return b["decile"], b["hit_rate"], b["lift"]
    return 10, 9.9, 0.80


def evaluate_stock_factor_score(
    stock_id: str = "",
    daily_k: Optional[pd.DataFrame] = None,
    monthly_revenue: Optional[pd.DataFrame] = None,
    institutional_investors: Optional[pd.DataFrame] = None,
    market_bull: bool = False,
    custom_rs_pct: Optional[float] = None,
    market_index_k: Optional[pd.DataFrame] = None,
    quarterly_financials: Optional[pd.DataFrame] = None,
    margin_short: Optional[pd.DataFrame] = None,
    as_of_date: Optional[str] = None,
    **kwargs,
) -> FactorScoreResult:
    """Evaluate empirical multi-factor score for a stock on the latest available trading day.

    Args:
        stock_id: Stock symbol.
        daily_k: Daily K bars DataFrame.
        monthly_revenue: Point-in-time monthly revenue records.
        institutional_investors: Institutional investors buy/sell records.
        market_bull: Whether overall market (TAIEX) is currently in bull mode.
        custom_rs_pct: Optional pre-calculated cross-sectional RS percentile rank in [0, 1].
        market_index_k: Optional market index DataFrame to evaluate market_bull automatically.
        quarterly_financials: Optional financials (reserved for compatibility).
        margin_short: Optional margin data.
        as_of_date: Optional reference evaluation date.
    """
    if daily_k is None or daily_k.empty or len(daily_k) < 20:
        return FactorScoreResult(
            factor_score=0.0,
            factor_decile=10,
            historical_hit_rate=9.9,
            historical_lift=0.80,
            triggered_factors=[],
            raw_score=0.0,
        )

    # Determine market_bull from market_index_k if not explicitly set True
    if not market_bull and market_index_k is not None and not market_index_k.empty and len(market_index_k) >= 60:
        idx_sorted = market_index_k.sort_values("date").reset_index(drop=True)
        if as_of_date:
            idx_sorted = idx_sorted[idx_sorted["date"] <= str(as_of_date)]
        if len(idx_sorted) >= 60:
            c = idx_sorted["close"].astype(float)
            ma20 = c.rolling(20).mean().iloc[-1]
            ma60 = c.rolling(60).mean().iloc[-1]
            last_idx_c = c.iloc[-1]
            if last_idx_c >= ma60 and ma20 >= ma60:
                market_bull = True

    df_ind = compute_all_indicators(daily_k)
    last_row = df_ind.iloc[-1]
    n = len(df_ind)

    triggered_keys: List[str] = []
    raw_score: float = 0.0

    # 1. Technical strategies
    strat_signals = evaluate_all_strategies(df_ind)
    if "帶量突破20日新高" in strat_signals and bool(strat_signals["帶量突破20日新高"].iloc[-1]):
        triggered_keys.append("strat_breakout_20d")
    if "布林通道壓縮突破" in strat_signals and bool(strat_signals["布林通道壓縮突破"].iloc[-1]):
        triggered_keys.append("strat_bb_breakout")

    # 2. Relative Strength RS
    # If custom_rs_pct provided (from cross-sectional scan pool), use it;
    # otherwise estimate based on 120-day return (>= 25% return proxy for RS top 20% in TWSE)
    is_rs_top20 = False
    if custom_rs_pct is not None:
        is_rs_top20 = custom_rs_pct >= 0.80
    else:
        if n >= 120:
            ret_120d = float(last_row["close"]) / float(df_ind.iloc[-120]["close"]) - 1.0
            is_rs_top20 = ret_120d >= 0.25

    if is_rs_top20:
        triggered_keys.append("rs_top20")

    # 3. Revenue factors (Point-in-Time)
    if monthly_revenue is not None and not monthly_revenue.empty:
        rf = compute_revenue_factors(df_ind[["date"]], monthly_revenue)
        if not rf.empty:
            last_rf = rf.iloc[-1]
            if bool(last_rf.get("rev_new_high")):
                triggered_keys.append("rev_new_high")
            if bool(last_rf.get("rev_accel")):
                triggered_keys.append("rev_accel")

        rev_yoy_df = compute_revenue_yoy(monthly_revenue)
        if not rev_yoy_df.empty and rev_yoy_df.iloc[-1]["revenue_yoy"] > 0:
            triggered_keys.append("rev_yoy_pos")

    # 4. Institutional factors
    if institutional_investors is not None and not institutional_investors.empty:
        chips = evaluate_chips_series(daily_k, institutional_investors, pd.DataFrame())
        if not chips.empty and bool(chips.iloc[-1]["foreign_trust_net_buy_10d"] > 0):
            triggered_keys.append("inst_net_pos")

        # Check volume ratio: 10d net buy shares / (vol_ma20 * 10) >= 0.05
        inst_daily = pd.merge(
            df_ind[["date"]],
            institutional_investors[["date", "foreign_buy", "foreign_sell", "investment_trust_buy", "investment_trust_sell"]],
            on="date",
            how="left",
        ).fillna(0.0)
        f_net = (inst_daily["foreign_buy"] - inst_daily["foreign_sell"]).astype(float)
        t_net = (inst_daily["investment_trust_buy"] - inst_daily["investment_trust_sell"]).astype(float)
        inst_10d_shares = (f_net + t_net).iloc[-10:].sum()
        vol_ma20 = float(last_row.get("vol_ma20", 0.0))
        if vol_ma20 > 0 and (inst_10d_shares / (vol_ma20 * 10.0)) >= 0.05:
            triggered_keys.append("inst_vol_ratio")

    # 5. Market Bull
    if market_bull:
        triggered_keys.append("market_bull")

    # Sum raw weights
    for k in triggered_keys:
        raw_score += FROZEN_FACTOR_WEIGHTS.get(k, 0.0)

    # Scale to 0 - 100
    norm_score = (raw_score - NORM_Q01) / (NORM_Q99 - NORM_Q01) * 100.0
    factor_score = float(np.clip(norm_score, 0.0, 100.0))

    decile, hit_rate, lift = score_to_decile(factor_score)

    display_tags = [FACTOR_DISPLAY_NAMES[k] for k in triggered_keys if k in FACTOR_DISPLAY_NAMES]

    return FactorScoreResult(
        factor_score=round(factor_score, 1),
        factor_decile=decile,
        historical_hit_rate=hit_rate,
        historical_lift=lift,
        triggered_factors=display_tags,
        raw_score=round(raw_score, 3),
    )
