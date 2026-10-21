"""Unit tests for Fundamental and Chips evaluation layers."""

import pandas as pd
import pytest

from app.analysis.layers import (
    compute_eps_4q_sum,
    compute_revenue_yoy,
    evaluate_chips_series,
    evaluate_fundamentals_series,
)


def test_fundamental_pass_scenario():
    """Scenario: 最近月營收年增 12%、近四季 EPS 合計 8.5 元、負債比 35% -> 通過."""
    daily_k = pd.DataFrame([
        {"date": "2024-09-20", "effective_date": "2024-09-20"},
    ])

    # Monthly revenue: 2023-08 is 100M, 2024-08 is 112M -> YoY = +12.0%
    monthly_revenue = pd.DataFrame([
        {"revenue_year": 2023, "revenue_month": 8, "revenue": 100.0, "effective_date": "2023-09-10"},
        {"revenue_year": 2024, "revenue_month": 8, "revenue": 112.0, "effective_date": "2024-09-10"},
    ])

    # Quarterly financials: 4 quarters sum to 8.5, debt ratio 35%
    quarterly_financials = pd.DataFrame([
        {"year": 2023, "quarter": 3, "eps": 2.0, "debt_ratio": 38.0, "effective_date": "2023-11-14"},
        {"year": 2023, "quarter": 4, "eps": 2.0, "debt_ratio": 36.0, "effective_date": "2024-03-31"},
        {"year": 2024, "quarter": 1, "eps": 2.2, "debt_ratio": 35.5, "effective_date": "2024-05-15"},
        {"year": 2024, "quarter": 2, "eps": 2.3, "debt_ratio": 35.0, "effective_date": "2024-08-14"},
    ])

    res = evaluate_fundamentals_series(daily_k, monthly_revenue, quarterly_financials)
    assert len(res) == 1
    row = res.iloc[0]

    assert bool(row["fundamental_pass"]) is True
    assert pytest.approx(row["revenue_yoy"], rel=1e-3) == 0.12
    assert pytest.approx(row["eps_4q_sum"], rel=1e-3) == 8.50
    assert pytest.approx(row["debt_ratio"], rel=1e-3) == 35.0
    assert row["fundamental_reason"] == ""


def test_fundamental_negative_eps_scenario():
    """Scenario: 近四季 EPS 合計為 −1.2 元 -> 未通過，原因顯示「近四季 EPS 合計 −1.20 元，不大於 0」."""
    daily_k = pd.DataFrame([{"date": "2024-09-20", "effective_date": "2024-09-20"}])

    monthly_revenue = pd.DataFrame([
        {"revenue_year": 2023, "revenue_month": 8, "revenue": 100.0, "effective_date": "2023-09-10"},
        {"revenue_year": 2024, "revenue_month": 8, "revenue": 105.0, "effective_date": "2024-09-10"},
    ])

    quarterly_financials = pd.DataFrame([
        {"year": 2023, "quarter": 3, "eps": -0.5, "debt_ratio": 40.0, "effective_date": "2023-11-14"},
        {"year": 2023, "quarter": 4, "eps": -0.3, "debt_ratio": 42.0, "effective_date": "2024-03-31"},
        {"year": 2024, "quarter": 1, "eps": -0.2, "debt_ratio": 45.0, "effective_date": "2024-05-15"},
        {"year": 2024, "quarter": 2, "eps": -0.2, "debt_ratio": 48.0, "effective_date": "2024-08-14"},
    ])

    res = evaluate_fundamentals_series(daily_k, monthly_revenue, quarterly_financials)
    row = res.iloc[0]

    assert bool(row["fundamental_pass"]) is False
    assert pytest.approx(row["eps_4q_sum"], rel=1e-3) == -1.2
    assert "近四季 EPS 合計 -1.20 元，不大於 0" in row["fundamental_reason"]


def test_fundamental_high_debt_and_negative_yoy():
    """Verify multiple fundamental failure messages combined."""
    daily_k = pd.DataFrame([{"date": "2024-09-20", "effective_date": "2024-09-20"}])

    monthly_revenue = pd.DataFrame([
        {"revenue_year": 2023, "revenue_month": 8, "revenue": 100.0, "effective_date": "2023-09-10"},
        {"revenue_year": 2024, "revenue_month": 8, "revenue": 90.0, "effective_date": "2024-09-10"},
    ])

    quarterly_financials = pd.DataFrame([
        {"year": 2023, "quarter": 3, "eps": 1.0, "debt_ratio": 50.0, "effective_date": "2023-11-14"},
        {"year": 2023, "quarter": 4, "eps": 1.0, "debt_ratio": 55.0, "effective_date": "2024-03-31"},
        {"year": 2024, "quarter": 1, "eps": 1.0, "debt_ratio": 58.0, "effective_date": "2024-05-15"},
        {"year": 2024, "quarter": 2, "eps": 1.0, "debt_ratio": 65.0, "effective_date": "2024-08-14"},
    ])

    res = evaluate_fundamentals_series(daily_k, monthly_revenue, quarterly_financials)
    row = res.iloc[0]

    assert bool(row["fundamental_pass"]) is False
    assert "最近月營收年增率 -10.0%，不大於 0" in row["fundamental_reason"]
    assert "最近一季負債比 65.0%，不小於 60%" in row["fundamental_reason"]


def test_chips_net_sell_scenario():
    """Scenario: 外資加投信近 10 日累計賣超 3,200 張 -> 判定未通過."""
    dates = [f"2024-09-{i:02d}" for i in range(1, 11)]
    daily_k = pd.DataFrame({"date": dates})

    # Total 3,200 lots sold = 3,200,000 shares sold over 10 days = 320,000 shares sold per day
    inst_data = [
        {
            "date": d,
            "foreign_buy": 0,
            "foreign_sell": 200_000,
            "investment_trust_buy": 0,
            "investment_trust_sell": 120_000,
        }
        for d in dates
    ]
    inst_df = pd.DataFrame(inst_data)
    margin_df = pd.DataFrame([{"date": d, "margin_purchase_balance": 1000} for d in dates])

    res = evaluate_chips_series(daily_k, inst_df, margin_df)
    last_row = res.iloc[-1]

    assert bool(last_row["chips_pass"]) is False
    assert "外資＋投信近 10 日賣超 3,200 張" in last_row["chips_reason"]


def test_chips_margin_spike_scenario():
    """Scenario: 融資餘額近 10 日增幅 >= 20% -> 判定未通過."""
    dates = [f"2024-09-{i:02d}" for i in range(1, 12)]
    daily_k = pd.DataFrame({"date": dates})

    # Net buy is positive: 100 lots per day
    inst_df = pd.DataFrame([
        {
            "date": d,
            "foreign_buy": 100_000,
            "foreign_sell": 0,
            "investment_trust_buy": 0,
            "investment_trust_sell": 0,
        }
        for d in dates
    ])

    # Margin balance: 10 days ago (index 0) was 1000, today (index 10) is 1250 -> +25%
    balances = [1000] * 10 + [1250]
    margin_df = pd.DataFrame([{"date": dates[i], "margin_purchase_balance": balances[i]} for i in range(11)])

    res = evaluate_chips_series(daily_k, inst_df, margin_df)
    last_row = res.iloc[-1]

    assert bool(last_row["chips_pass"]) is False
    assert "融資餘額近 10 日增幅 25.0%，不小於 20%" in last_row["chips_reason"]


def test_chips_pass_scenario():
    """Scenario: 外資加投信買超且融資增幅未超標 -> 通過."""
    dates = [f"2024-09-{i:02d}" for i in range(1, 12)]
    daily_k = pd.DataFrame({"date": dates})

    inst_df = pd.DataFrame([
        {
            "date": d,
            "foreign_buy": 500_000,
            "foreign_sell": 0,
            "investment_trust_buy": 0,
            "investment_trust_sell": 0,
        }
        for d in dates
    ])
    margin_df = pd.DataFrame([{"date": d, "margin_purchase_balance": 1000} for d in dates])

    res = evaluate_chips_series(daily_k, inst_df, margin_df)
    last_row = res.iloc[-1]

    assert bool(last_row["chips_pass"]) is True
    assert last_row["chips_reason"] == ""
