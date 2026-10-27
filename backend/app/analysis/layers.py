"""Fundamental and chips layer evaluation sequences for Taiwan stock analysis.

All evaluations are point-in-time correct using `effective_date` and `pd.merge_asof`.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from app.analysis import params


@dataclass
class FundamentalEvaluation:
    """Fundamental layer evaluation result for a single day."""

    passed: bool
    revenue_yoy: Optional[float]
    eps_4q_sum: Optional[float]
    debt_ratio: Optional[float]
    reason: str


@dataclass
class ChipsEvaluation:
    """Chips layer evaluation result for a single day."""

    passed: bool
    foreign_trust_net_buy_10d: Optional[float]  # in lots (張)
    margin_increase_rate_10d: Optional[float]  # e.g. 0.15 for 15%
    reason: str


def compute_revenue_yoy(monthly_revenue: pd.DataFrame) -> pd.DataFrame:
    """Compute YoY revenue growth for each monthly revenue record.

    Matches (year, month) with (year - 1, month).
    """
    if monthly_revenue.empty:
        df = monthly_revenue.copy()
        df["revenue_yoy"] = pd.Series(dtype=float)
        return df

    df = monthly_revenue.copy()
    # Normalize types
    df["revenue_year"] = df["revenue_year"].astype(int)
    df["revenue_month"] = df["revenue_month"].astype(int)
    df["revenue"] = df["revenue"].astype(float)

    # Build lookup map: (year, month) -> revenue
    lookup = {
        (row.revenue_year, row.revenue_month): row.revenue
        for row in df.itertuples(index=False)
    }

    yoy_values = []
    for row in df.itertuples(index=False):
        prev_rev = lookup.get((row.revenue_year - 1, row.revenue_month))
        if prev_rev is not None and prev_rev > 0:
            yoy = (row.revenue - prev_rev) / prev_rev
        else:
            yoy = np.nan
        yoy_values.append(yoy)

    df["revenue_yoy"] = yoy_values
    return df


def compute_eps_4q_sum(quarterly_financials: pd.DataFrame) -> pd.DataFrame:
    """Compute trailing 4-quarters EPS sum for each quarterly record."""
    if quarterly_financials.empty:
        df = quarterly_financials.copy()
        df["eps_4q_sum"] = pd.Series(dtype=float)
        return df

    df = quarterly_financials.copy()
    df["year"] = df["year"].astype(int)
    df["quarter"] = df["quarter"].astype(int)
    df["eps"] = df["eps"].astype(float)
    df["debt_ratio"] = df["debt_ratio"].astype(float)

    # Sort chronologically by year and quarter
    df = df.sort_values(["year", "quarter"]).reset_index(drop=True)
    df["eps_4q_sum"] = df["eps"].rolling(window=4, min_periods=4).sum()
    return df


def evaluate_fundamentals_series(
    daily_k: pd.DataFrame,
    monthly_revenue: pd.DataFrame,
    quarterly_financials: pd.DataFrame,
) -> pd.DataFrame:
    """Generate daily fundamental evaluation series aligned with daily_k dates using merge_asof.

    Returns DataFrame with columns:
    ['date', 'fundamental_pass', 'revenue_yoy', 'eps_4q_sum', 'debt_ratio', 'fundamental_reason']
    """
    if daily_k.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "fundamental_pass",
                "revenue_yoy",
                "eps_4q_sum",
                "debt_ratio",
                "fundamental_reason",
            ]
        )

    # Prepare daily dates
    daily = daily_k[["date"]].copy()
    if "effective_date" in daily_k.columns:
        daily["effective_date"] = daily_k["effective_date"]
    else:
        daily["effective_date"] = daily_k["date"]

    daily["effective_date_dt"] = pd.to_datetime(daily["effective_date"])
    daily = daily.sort_values("effective_date_dt").reset_index(drop=True)

    # Prepare monthly revenue with YoY
    rev_df = compute_revenue_yoy(monthly_revenue)
    if not rev_df.empty:
        rev_df["effective_date_dt"] = pd.to_datetime(rev_df["effective_date"])
        # Dedup keeping the latest publication
        rev_df = (
            rev_df.sort_values("effective_date_dt")
            .drop_duplicates(subset=["effective_date_dt"], keep="last")[
                ["effective_date_dt", "revenue_yoy"]
            ]
            .dropna(subset=["effective_date_dt"])
        )
    else:
        rev_df = pd.DataFrame({
            "effective_date_dt": pd.Series(dtype="datetime64[ns]"),
            "revenue_yoy": pd.Series(dtype=float),
        })

    # Prepare quarterly financials with 4Q EPS sum
    q_df = compute_eps_4q_sum(quarterly_financials)
    if not q_df.empty:
        q_df["effective_date_dt"] = pd.to_datetime(q_df["effective_date"])
        q_df = (
            q_df.sort_values("effective_date_dt")
            .drop_duplicates(subset=["effective_date_dt"], keep="last")[
                ["effective_date_dt", "eps_4q_sum", "debt_ratio"]
            ]
            .dropna(subset=["effective_date_dt"])
        )
    else:
        q_df = pd.DataFrame({
            "effective_date_dt": pd.Series(dtype="datetime64[ns]"),
            "eps_4q_sum": pd.Series(dtype=float),
            "debt_ratio": pd.Series(dtype=float),
        })

    # As-of joins
    merged = daily.copy()
    if not rev_df.empty:
        merged = pd.merge_asof(
            merged,
            rev_df,
            on="effective_date_dt",
            direction="backward",
        )
    else:
        merged["revenue_yoy"] = np.nan

    if not q_df.empty:
        merged = pd.merge_asof(
            merged,
            q_df,
            on="effective_date_dt",
            direction="backward",
        )
    else:
        merged["eps_4q_sum"] = np.nan
        merged["debt_ratio"] = np.nan

    passes = []
    reasons = []

    for _, r in merged.iterrows():
        yoy = r["revenue_yoy"]
        eps_sum = r["eps_4q_sum"]
        debt = r["debt_ratio"]

        fails = []
        # Check EPS sum
        if pd.isna(eps_sum):
            fails.append("近四季 EPS 資料不足")
        elif eps_sum <= params.EPS_4Q_SUM_MIN:
            fails.append(f"近四季 EPS 合計 {eps_sum:.2f} 元，不大於 0")

        # Check Revenue YoY
        if pd.isna(yoy):
            fails.append("月營收資料不足")
        elif yoy <= params.REVENUE_YOY_MIN:
            fails.append(f"最近月營收年增率 {yoy * 100:.1f}%，不大於 0")

        # Check Debt Ratio
        if pd.isna(debt):
            fails.append("負債比資料不足")
        elif debt >= params.DEBT_RATIO_MAX:
            fails.append(f"最近一季負債比 {debt:.1f}%，不小於 60%")

        if fails:
            passes.append(False)
            reasons.append("；".join(fails))
        else:
            passes.append(True)
            reasons.append("")

    merged["fundamental_pass"] = [bool(p) for p in passes]
    merged["fundamental_reason"] = reasons

    return merged[
        [
            "date",
            "fundamental_pass",
            "revenue_yoy",
            "eps_4q_sum",
            "debt_ratio",
            "fundamental_reason",
        ]
    ]


def evaluate_chips_series(
    daily_k: pd.DataFrame,
    institutional_investors: pd.DataFrame,
    margin_short: pd.DataFrame,
) -> pd.DataFrame:
    """Generate daily chips evaluation series aligned with daily_k dates.

    Conditions:
    1. Foreign + Investment Trust net buy over past 10 trading days > 0 lots (張)
    2. Margin balance increase over past 10 trading days < 20%

    Returns DataFrame with columns:
    ['date', 'chips_pass', 'foreign_trust_net_buy_10d', 'margin_increase_rate_10d', 'chips_reason']
    """
    if daily_k.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "chips_pass",
                "foreign_trust_net_buy_10d",
                "margin_increase_rate_10d",
                "chips_reason",
            ]
        )

    daily = daily_k[["date"]].copy().sort_values("date").reset_index(drop=True)

    # 1. Institutional Investors
    if not institutional_investors.empty:
        inst = institutional_investors.copy()
        # Compute daily net buy shares of Foreign + Investment Trust
        # Note: 1 lot (張) = 1000 shares (股)
        f_net = inst["foreign_buy"].fillna(0) - inst["foreign_sell"].fillna(0)
        t_net = inst["investment_trust_buy"].fillna(0) - inst["investment_trust_sell"].fillna(0)
        inst["inst_net_lots"] = (f_net + t_net) / 1000.0

        daily_inst = pd.merge(daily[["date"]], inst[["date", "inst_net_lots"]], on="date", how="left")
        daily_inst["inst_net_lots"] = daily_inst["inst_net_lots"].fillna(0.0)
    else:
        daily_inst = daily[["date"]].copy()
        daily_inst["inst_net_lots"] = 0.0

    # 10 trading days rolling sum of net buy
    inst_10d = daily_inst["inst_net_lots"].rolling(window=params.INSTITUTIONAL_LOOKBACK_DAYS, min_periods=1).sum()

    # 2. Margin balance
    if not margin_short.empty:
        margin = margin_short.copy()
        daily_margin = pd.merge(
            daily[["date"]],
            margin[["date", "margin_purchase_balance"]],
            on="date",
            how="left",
        )
        daily_margin["margin_purchase_balance"] = daily_margin["margin_purchase_balance"].ffill().fillna(0.0)
    else:
        daily_margin = daily[["date"]].copy()
        daily_margin["margin_purchase_balance"] = 0.0

    balance = daily_margin["margin_purchase_balance"]
    prev_balance_10d = balance.shift(params.MARGIN_LOOKBACK_DAYS)

    # Calculate percentage increase
    margin_inc_rate = pd.Series(index=daily.index, dtype=float)
    for i in range(len(daily)):
        p10 = prev_balance_10d.iloc[i]
        curr = balance.iloc[i]
        if pd.isna(p10) or p10 == 0:
            # If no history from 10 days ago, no spike detected
            margin_inc_rate.iloc[i] = 0.0
        else:
            margin_inc_rate.iloc[i] = (curr - p10) / p10

    passes = []
    reasons = []

    for i in range(len(daily)):
        inst_lots = inst_10d.iloc[i]
        m_rate = margin_inc_rate.iloc[i]

        fails = []
        # Check institutional net buy
        if inst_lots <= params.INSTITUTIONAL_NET_BUY_MIN:
            if inst_lots < 0:
                fails.append(f"外資＋投信近 10 日賣超 {abs(inst_lots):,.0f} 張")
            else:
                fails.append("外資＋投信近 10 日累計買超不大於 0 張")

        # Check margin increase rate
        if m_rate >= params.MARGIN_INCREASE_RATE_MAX:
            fails.append(f"融資餘額近 10 日增幅 {m_rate * 100:.1f}%，不小於 20%")

        if fails:
            passes.append(False)
            reasons.append("；".join(fails))
        else:
            passes.append(True)
            reasons.append("")

    res = pd.DataFrame({
        "date": daily["date"],
        "chips_pass": [bool(p) for p in passes],
        "foreign_trust_net_buy_10d": inst_10d,
        "margin_increase_rate_10d": margin_inc_rate,
        "chips_reason": reasons,
    })
    return res
