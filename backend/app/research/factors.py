"""Factor calculation and panel building for stock factor event study."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from app.analysis.indicators import compute_all_indicators
from app.analysis.layers import (
    compute_eps_4q_sum,
    compute_revenue_yoy,
    evaluate_chips_series,
    evaluate_fundamentals_series,
)
from app.analysis.strategies import evaluate_all_strategies
from app.data.cache import CacheRepository
from app.research.config import StudyConfig
from app.research.labels import compute_forward_labels


def compute_market_bull_series(
    taiex_k: pd.DataFrame,
    config: Optional[StudyConfig] = None,
) -> pd.DataFrame:
    """Compute market bull indicator on TAIEX index series.

    Conditions:
    1. TAIEX close > MA60
    2. MA60[t] > MA60[t-20]
    """
    cfg = config or StudyConfig()
    if taiex_k.empty or len(taiex_k) < cfg.market_ma_window:
        return pd.DataFrame(columns=["date", "market_bull"])

    df = taiex_k[["date", "close"]].copy().sort_values("date").reset_index(drop=True)
    df["close"] = df["close"].astype(float)
    df["ma60"] = df["close"].rolling(cfg.market_ma_window, min_periods=cfg.market_ma_window).mean()
    df["ma60_prev"] = df["ma60"].shift(cfg.market_ma_slope_window)

    bull = (df["close"] > df["ma60"]) & (df["ma60"] > df["ma60_prev"])
    df["market_bull"] = bull.fillna(False)
    return df[["date", "market_bull"]]


def compute_revenue_factors(
    daily_dates: pd.DataFrame,
    monthly_revenue: pd.DataFrame,
    config: Optional[StudyConfig] = None,
) -> pd.DataFrame:
    """Compute monthly revenue factors and merge as-of daily dates.

    Factors:
    - rev_accel: mean YoY(3m) > mean YoY(12m)
    - rev_new_high: monthly revenue >= max(revenue of prior 24 months)
    """
    cfg = config or StudyConfig()
    daily = daily_dates[["date"]].copy()
    if "effective_date" in daily_dates.columns:
        daily["effective_date"] = daily_dates["effective_date"]
    else:
        daily["effective_date"] = daily_dates["date"]
    daily["effective_date_dt"] = pd.to_datetime(daily["effective_date"])
    daily = daily.sort_values("effective_date_dt").reset_index(drop=True)

    if monthly_revenue.empty:
        daily["rev_accel"] = False
        daily["rev_new_high"] = False
        return daily[["date", "rev_accel", "rev_new_high"]]

    rev_df = compute_revenue_yoy(monthly_revenue)
    rev_df = rev_df.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)

    yoy = rev_df["revenue_yoy"].astype(float)
    rev = rev_df["revenue"].astype(float)

    # 3m vs 12m rolling mean of YoY
    yoy_3m = yoy.rolling(cfg.rev_accel_fast_months, min_periods=cfg.rev_accel_fast_months).mean()
    yoy_12m = yoy.rolling(cfg.rev_accel_slow_months, min_periods=cfg.rev_accel_slow_months).mean()
    rev_df["rev_accel"] = (yoy_3m > yoy_12m).fillna(False)

    # Past 24 months max revenue
    prior_24m_max = rev.shift(1).rolling(cfg.rev_new_high_lookback_months, min_periods=12).max()
    rev_df["rev_new_high"] = (rev >= prior_24m_max).fillna(False)

    rev_df["effective_date_dt"] = pd.to_datetime(rev_df["effective_date"])
    # Dedup keeping the latest publication
    rev_clean = (
        rev_df.sort_values("effective_date_dt")
        .drop_duplicates(subset=["effective_date_dt"], keep="last")[
            ["effective_date_dt", "rev_accel", "rev_new_high"]
        ]
        .dropna(subset=["effective_date_dt"])
    )

    if rev_clean.empty:
        daily["rev_accel"] = False
        daily["rev_new_high"] = False
        return daily[["date", "rev_accel", "rev_new_high"]]

    rev_clean["effective_date_dt"] = rev_clean["effective_date_dt"].astype(daily["effective_date_dt"].dtype)

    merged = pd.merge_asof(
        daily,
        rev_clean,
        on="effective_date_dt",
        direction="backward",
    )
    merged["rev_accel"] = merged["rev_accel"].fillna(False).astype(bool)
    merged["rev_new_high"] = merged["rev_new_high"].fillna(False).astype(bool)
    return merged[["date", "rev_accel", "rev_new_high"]]


def compute_stock_factors(
    stock_id: str,
    daily_k: pd.DataFrame,
    institutional_investors: pd.DataFrame,
    margin_short: pd.DataFrame,
    monthly_revenue: pd.DataFrame,
    quarterly_financials: pd.DataFrame,
    market_bull_df: Optional[pd.DataFrame] = None,
    config: Optional[StudyConfig] = None,
) -> pd.DataFrame:
    """Compute all single-stock factors, forward labels, and hard exclusion status.

    Returns DataFrame aligned with daily_k dates.
    """
    cfg = config or StudyConfig()
    if daily_k.empty or len(daily_k) < 35:
        return pd.DataFrame()

    df_ind = compute_all_indicators(daily_k)
    df_ind = df_ind.sort_values("date").reset_index(drop=True)
    n = len(df_ind)

    # 1. Forward labels
    df_labels = compute_forward_labels(daily_k, config=cfg)

    # 2. 5 Technical strategies
    strat_signals = evaluate_all_strategies(df_ind)
    strat_keys = {
        "strat_ma_pullback": "均線多頭排列下拉回20MA",
        "strat_breakout_20d": "帶量突破20日新高",
        "strat_macd_cross": "MACD黃金交叉",
        "strat_kd_cross": "KD低檔黃金交叉",
        "strat_bb_breakout": "布林通道壓縮突破",
    }
    strat_cols = {}
    for col, name in strat_keys.items():
        if name in strat_signals:
            strat_cols[col] = strat_signals[name].values
        else:
            strat_cols[col] = np.zeros(n, dtype=bool)

    # 3. Fundamental and chips series (point-in-time)
    fund_df = evaluate_fundamentals_series(daily_k, monthly_revenue, quarterly_financials)
    chips_df = evaluate_chips_series(daily_k, institutional_investors, margin_short)

    fund_merged = pd.merge(df_ind[["date"]], fund_df, on="date", how="left")
    chips_merged = pd.merge(df_ind[["date"]], chips_df, on="date", how="left")

    rev_yoy = fund_merged["revenue_yoy"].astype(float)
    eps_sum = fund_merged["eps_4q_sum"].astype(float)
    debt_ratio = fund_merged["debt_ratio"].astype(float)
    inst_net_lots = chips_merged["foreign_trust_net_buy_10d"].astype(float)
    margin_inc = chips_merged["margin_increase_rate_10d"].astype(float)

    rev_yoy_pos = (rev_yoy > 0.0).fillna(False)
    debt_ok = (debt_ratio < cfg.debt_ratio_max).fillna(False)
    inst_net_pos = (inst_net_lots > 0.0).fillna(False)

    # Hard exclusion filter: EPS 4Q <= 0 or margin spike >= 20%
    eps_bad = eps_sum.isna() | (eps_sum <= cfg.eps_sum_min)
    margin_bad = margin_inc.fillna(0.0) >= cfg.margin_inc_max
    hard_exclude = (eps_bad | margin_bad).values

    # 4. VCP factor
    close = df_ind["close"].astype(float)
    volume = df_ind["volume"].astype(float)
    atr = df_ind["atr14"].astype(float)

    atr_ratio = atr / close
    atr_ratio_prev = atr_ratio.shift(cfg.vcp_atr_ratio_lookback)
    atr_decay = (atr_ratio < (atr_ratio_prev * cfg.vcp_atr_ratio_decay)).fillna(False)

    vol_ma5 = volume.rolling(cfg.vcp_vol_fast, min_periods=cfg.vcp_vol_fast).mean()
    vol_ma50 = volume.rolling(cfg.vcp_vol_slow, min_periods=cfg.vcp_vol_slow).mean()
    vol_contract = (vol_ma5 < vol_ma50).fillna(False)

    high_250 = close.rolling(cfg.vcp_high_lookback, min_periods=50).max()
    near_high = (close >= (high_250 * cfg.vcp_high_pct)).fillna(False)
    vcp = (atr_decay & vol_contract & near_high).values

    # 5. Institutional trust streak and volume ratio
    inst_daily = pd.merge(
        df_ind[["date"]],
        institutional_investors[["date", "foreign_buy", "foreign_sell", "investment_trust_buy", "investment_trust_sell"]]
        if not institutional_investors.empty else pd.DataFrame(columns=["date", "foreign_buy", "foreign_sell", "investment_trust_buy", "investment_trust_sell"]),
        on="date",
        how="left",
    ).fillna(0.0)

    trust_net = (inst_daily["investment_trust_buy"] - inst_daily["investment_trust_sell"]).astype(float)
    trust_pos = (trust_net > 0.0).astype(int)
    trust_streak3 = (trust_pos.rolling(cfg.trust_streak_days, min_periods=cfg.trust_streak_days).sum() == cfg.trust_streak_days).fillna(False).values

    f_net = (inst_daily["foreign_buy"] - inst_daily["foreign_sell"]).astype(float)
    inst_10d_shares = (f_net + trust_net).rolling(cfg.inst_vol_ratio_days, min_periods=cfg.inst_vol_ratio_days).sum()
    vol_ma20 = volume.rolling(20, min_periods=20).mean()
    inst_vol_ratio = ((inst_10d_shares / (vol_ma20 * 10.0)) >= cfg.inst_vol_ratio_min).fillna(False).values

    # 6. Revenue factors
    rev_factors = compute_revenue_factors(df_ind[["date"]], monthly_revenue, config=cfg)
    rev_factors_merged = pd.merge(df_ind[["date"]], rev_factors, on="date", how="left")

    # 7. Market bull
    if market_bull_df is not None and not market_bull_df.empty:
        mkt_merged = pd.merge(df_ind[["date"]], market_bull_df, on="date", how="left")
        market_bull = mkt_merged["market_bull"].fillna(False).values
    else:
        market_bull = np.zeros(n, dtype=bool)

    # 8. 120-day return for RS calculation
    ret_120d = (close / close.shift(cfg.rs_return_window) - 1.0).values

    # Assemble stock panel
    df_res = pd.DataFrame({
        "stock_id": stock_id,
        "date": df_ind["date"].astype(str),
        "close": close.values,
        "ret_120d": ret_120d,
        "forward_hit": df_labels["forward_hit"].values,
        "forward_valid": df_labels["forward_valid"].values,
        "exclude_reason": df_labels["exclude_reason"].values,
        "hard_exclude": hard_exclude,
        # Factors
        "strat_ma_pullback": strat_cols["strat_ma_pullback"],
        "strat_breakout_20d": strat_cols["strat_breakout_20d"],
        "strat_macd_cross": strat_cols["strat_macd_cross"],
        "strat_kd_cross": strat_cols["strat_kd_cross"],
        "strat_bb_breakout": strat_cols["strat_bb_breakout"],
        "rev_yoy_pos": rev_yoy_pos.values,
        "debt_ok": debt_ok.values,
        "inst_net_pos": inst_net_pos.values,
        "market_bull": market_bull,
        "vcp": vcp,
        "trust_streak3": trust_streak3,
        "inst_vol_ratio": inst_vol_ratio,
        "rev_accel": rev_factors_merged["rev_accel"].values,
        "rev_new_high": rev_factors_merged["rev_new_high"].values,
    })

    return df_res


def build_panel(
    repo: CacheRepository,
    stock_ids: Optional[List[str]] = None,
    config: Optional[StudyConfig] = None,
) -> pd.DataFrame:
    """Build cross-sectional factor panel for all specified or cached stocks."""
    cfg = config or StudyConfig()
    ids = stock_ids or repo.get_cached_stock_ids()

    # Load market index TAIEX
    taiex_k = repo.get_market_index("TAIEX")
    market_bull_df = compute_market_bull_series(taiex_k, config=cfg)

    stock_dfs = []
    for sid in ids:
        daily_k = repo.get_daily_k(sid)
        if daily_k.empty or len(daily_k) < 35:
            continue
        inst = repo.get_institutional_investors(sid)
        margin = repo.get_margin_short(sid)
        rev = repo.get_monthly_revenue(sid)
        fin = repo.get_quarterly_financials(sid)

        sdf = compute_stock_factors(
            stock_id=sid,
            daily_k=daily_k,
            institutional_investors=inst,
            margin_short=margin,
            monthly_revenue=rev,
            quarterly_financials=fin,
            market_bull_df=market_bull_df,
            config=cfg,
        )
        if not sdf.empty:
            stock_dfs.append(sdf)

    if not stock_dfs:
        return pd.DataFrame()

    panel = pd.concat(stock_dfs, ignore_index=True)

    # Cross-sectional Relative Strength RS percentile rank
    # Note: rank(pct=True) is grouped by date
    panel["rs_pct"] = panel.groupby("date")["ret_120d"].rank(pct=True)
    panel["rs_top20"] = (panel["rs_pct"] >= cfg.rs_percentile_min).fillna(False).values

    return panel
