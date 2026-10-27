"""Unit tests for factor calculations and point-in-time alignments."""

import numpy as np
import pandas as pd
import pytest

from app.research.config import StudyConfig
from app.research.factors import (
    compute_market_bull_series,
    compute_revenue_factors,
    compute_stock_factors,
)


def _make_daily_k(n: int = 150, start_date: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start_date, periods=n, freq="B").strftime("%Y-%m-%d")
    prices = 100.0 + np.arange(n) * 0.1
    return pd.DataFrame({
        "stock_id": "TEST",
        "date": dates,
        "open": prices,
        "high": prices + 1.0,
        "low": prices - 1.0,
        "close": prices,
        "volume": [1000000.0] * n,
    })


def test_market_bull_factor():
    """Scenario: 加權指數站上 60MA 且 60MA 上揚 -> market_bull=True."""
    # Build 100 days with rising index
    dates = pd.date_range("2024-01-01", periods=100, freq="B").strftime("%Y-%m-%d")
    closes = np.linspace(15000, 18000, 100)
    taiex = pd.DataFrame({"date": dates, "close": closes})

    res = compute_market_bull_series(taiex)
    # At day 90, close is well above 60MA and MA60 is rising
    assert bool(res.loc[90, "market_bull"]) is True

    # Build falling index
    closes_fall = np.linspace(18000, 14000, 100)
    taiex_fall = pd.DataFrame({"date": dates, "close": closes_fall})
    res_fall = compute_market_bull_series(taiex_fall)
    assert bool(res_fall.loc[90, "market_bull"]) is False


def test_vcp_factor():
    """Scenario: 波動度收斂、量縮、接近高點 -> vcp=True."""
    df_k = _make_daily_k(300)
    # Modify recent days to simulate VCP:
    # 1. Close near 250d high (max close is around day 299)
    # 2. Lower volume in last 10 days
    df_k.loc[280:, "volume"] = 100000.0  # 1/10 of earlier 1,000,000 volume
    # 3. Very small range in last 10 days (tight ATR)
    for i in range(280, 300):
        c = df_k.loc[i, "close"]
        df_k.loc[i, "high"] = c + 0.05
        df_k.loc[i, "low"] = c - 0.05

    sdf = compute_stock_factors(
        stock_id="TEST",
        daily_k=df_k,
        institutional_investors=pd.DataFrame(),
        margin_short=pd.DataFrame(),
        monthly_revenue=pd.DataFrame(),
        quarterly_financials=pd.DataFrame(),
    )
    assert bool(sdf.loc[295, "vcp"]) is True


def test_trust_streak_and_vol_ratio():
    """Scenario: 投信連續 3 日買超，以及法人買超佔 20 日均量 >= 5%."""
    df_k = _make_daily_k(60)
    dates = df_k["date"].tolist()

    # Create institutional records with streak on days 40, 41, 42
    inst_rows = []
    for i, d in enumerate(dates):
        if i in (40, 41, 42):
            inst_rows.append({
                "date": d,
                "foreign_buy": 100000.0,
                "foreign_sell": 0.0,
                "investment_trust_buy": 50000.0,
                "investment_trust_sell": 0.0,
            })
        else:
            inst_rows.append({
                "date": d,
                "foreign_buy": 0.0,
                "foreign_sell": 0.0,
                "investment_trust_buy": 0.0,
                "investment_trust_sell": 0.0,
            })
    inst_df = pd.DataFrame(inst_rows)

    sdf = compute_stock_factors(
        stock_id="TEST",
        daily_k=df_k,
        institutional_investors=inst_df,
        margin_short=pd.DataFrame(),
        monthly_revenue=pd.DataFrame(),
        quarterly_financials=pd.DataFrame(),
    )
    # Day 42 should have trust_streak3 = True
    assert bool(sdf.loc[42, "trust_streak3"]) is True
    # Day 39 should be False
    assert bool(sdf.loc[39, "trust_streak3"]) is False


def test_revenue_point_in_time():
    """Scenario: 營收尚未公告時 (effective_date 前)，不得使用最新公布的營收."""
    dates_df = pd.DataFrame({
        "date": ["2024-03-05", "2024-03-08", "2024-03-11", "2024-03-15"],
        "effective_date": ["2024-03-05", "2024-03-08", "2024-03-11", "2024-03-15"],
    })

    # Past 24 months revenue flat 150, Jan 2024 is 100 (< 150), Feb 2024 explodes to 500 (new high)
    rows = []
    for y in (2022, 2023):
        for m in range(1, 13):
            rows.append({
                "revenue_year": y,
                "revenue_month": m,
                "revenue": 150.0,
                "effective_date": f"{y}-{m+1:02d}-10" if m < 12 else f"{y+1}-01-10",
            })
    # Add Jan 2024
    rows.append({
        "revenue_year": 2024,
        "revenue_month": 1,
        "revenue": 100.0,
        "effective_date": "2024-02-10",
    })
    # Add Feb 2024 (record revenue, effective on 2024-03-10)
    rows.append({
        "revenue_year": 2024,
        "revenue_month": 2,
        "revenue": 500.0,
        "effective_date": "2024-03-10",
    })
    rev_df = pd.DataFrame(rows)

    res = compute_revenue_factors(dates_df, rev_df)
    # On 2024-03-08 (before effective_date 2024-03-10): cannot see Feb revenue
    row_0308 = res[res["date"] == "2024-03-08"].iloc[0]
    assert bool(row_0308["rev_new_high"]) is False

    # On 2024-03-11 (after effective_date 2024-03-10): sees Feb revenue
    row_0311 = res[res["date"] == "2024-03-11"].iloc[0]
    assert bool(row_0311["rev_new_high"]) is True
