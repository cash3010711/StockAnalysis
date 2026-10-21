"""Unit tests for today's three-layer analysis assembly."""

import pandas as pd
import pytest

from app.analysis import params
from app.analysis.assembler import assemble_today_analysis


def _create_mock_datasets(
    n_days: int = 35,
    last_close: float = 100.0,
    last_high: float = 102.0,
    last_low: float = 98.0,
    last_volume: float = 2000.0,
    prev_high_max: float = 152.5,
    fundamental_pass: bool = True,
    chips_pass: bool = True,
):
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B").strftime("%Y-%m-%d").tolist()
    daily_k = pd.DataFrame({
        "date": dates,
        "open": [100.0] * n_days,
        "high": [101.0] * n_days,
        "low": [99.0] * n_days,
        "close": [100.0] * n_days,
        "volume": [1000.0] * n_days,
        "effective_date": dates,
    })

    # Set 20-day high max in history
    daily_k.loc[15, "high"] = prev_high_max

    # Set last day
    daily_k.loc[n_days - 1, "close"] = last_close
    daily_k.loc[n_days - 1, "high"] = last_high
    daily_k.loc[n_days - 1, "low"] = last_low
    daily_k.loc[n_days - 1, "volume"] = last_volume

    # Monthly revenue (both effective before dates start in 2024)
    yoy_mult = 1.15 if fundamental_pass else 0.85
    monthly_revenue = pd.DataFrame([
        {"revenue_year": 2022, "revenue_month": 12, "revenue": 100.0, "effective_date": "2023-01-10"},
        {"revenue_year": 2023, "revenue_month": 12, "revenue": 100.0 * yoy_mult, "effective_date": "2024-01-10"},
    ])

    # Quarterly financials
    eps_val = 2.0 if fundamental_pass else -0.5
    debt_val = 35.0 if fundamental_pass else 75.0
    quarterly_financials = pd.DataFrame([
        {"year": 2022, "quarter": 4, "eps": eps_val, "debt_ratio": debt_val, "effective_date": "2023-03-31"},
        {"year": 2023, "quarter": 1, "eps": eps_val, "debt_ratio": debt_val, "effective_date": "2023-05-15"},
        {"year": 2023, "quarter": 2, "eps": eps_val, "debt_ratio": debt_val, "effective_date": "2023-08-14"},
        {"year": 2023, "quarter": 3, "eps": eps_val, "debt_ratio": debt_val, "effective_date": "2023-11-14"},
    ])

    # Institutional: positive or negative
    f_buy = 200_000 if chips_pass else 0
    f_sell = 0 if chips_pass else 500_000
    institutional_investors = pd.DataFrame([
        {
            "date": d,
            "foreign_buy": f_buy,
            "foreign_sell": f_sell,
            "investment_trust_buy": 0,
            "investment_trust_sell": 0,
            "effective_date": d,
        }
        for d in dates
    ])

    # Margin balance
    margin_short = pd.DataFrame([
        {"date": d, "margin_purchase_balance": 1000, "effective_date": d}
        for d in dates
    ])

    return daily_k, monthly_revenue, quarterly_financials, institutional_investors, margin_short


def test_scenario_only_technical_fails_trigger_given():
    """Scenario: 只差技術面 - 基本面、籌碼面通過，但收盤 148 元低於前 20 日最高價 152.5 元.

    THEN 「帶量突破」策略顯示「觀望：收盤站上 152.5 且量大於 1.5 倍均量才觸發」
    """
    daily_k, rev, qf, inst, margin = _create_mock_datasets(
        last_close=148.0,
        prev_high_max=152.5,
        fundamental_pass=True,
        chips_pass=True,
    )

    analysis = assemble_today_analysis("2330", daily_k, rev, qf, inst, margin)

    assert analysis.fundamental.passed is True
    assert analysis.chips.passed is True

    # Find breakout strategy
    breakout_strat = next(s for s in analysis.strategies if s.strategy_name == params.STRATEGY_BREAKOUT_20D)
    assert breakout_strat.status == "觀望"
    assert breakout_strat.entry_price is None
    assert breakout_strat.trigger_condition == "觀望：收盤站上 152.5 且量大於 1.5 倍均量才觸發"


def test_scenario_fundamental_fails_no_trigger_prices():
    """Scenario: 基本面未通過.

    THEN 所有策略都顯示「觀望」，並在最上方顯示基本面未通過的原因，不給出觸發價位
    """
    daily_k, rev, qf, inst, margin = _create_mock_datasets(
        last_close=155.0,
        prev_high_max=150.0,
        fundamental_pass=False,  # negative EPS and high debt!
        chips_pass=True,
    )

    analysis = assemble_today_analysis("2330", daily_k, rev, qf, inst, margin)

    assert analysis.fundamental.passed is False
    assert "不大於 0" in analysis.fundamental.reason or "不小於 60%" in analysis.fundamental.reason

    for s in analysis.strategies:
        assert s.status == "觀望"
        assert s.entry_price is None
        assert s.trigger_condition is None  # 不給出觸發價位!


def test_scenario_entry_levels_generated():
    """Scenario: 產生進場點位 - 三層皆通過，收盤價 100 元，ATR(14) 約 3 元.

    THEN 系統顯示進場參考價 100、停損 94、停利 109、最長持有 20 個交易日
    """
    n_days = 30
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B").strftime("%Y-%m-%d").tolist()
    daily_k = pd.DataFrame({
        "date": dates,
        "open": [97.0] * n_days,
        "high": [99.0] * n_days,
        "low": [96.0] * n_days,  # high - low = 3.0, prev_close = 97.0 -> TR = 3.0
        "close": [97.0] * n_days,
        "volume": [1000.0] * n_days,
        "effective_date": dates,
    })

    # Day 29: Breaks out above prior high 99.0 with close 100.0
    daily_k.loc[n_days - 1, "open"] = 98.0
    daily_k.loc[n_days - 1, "high"] = 101.0
    daily_k.loc[n_days - 1, "low"] = 98.0  # high - low = 3.0, |101 - 97| = 4, |98 - 97| = 1 -> TR = 4 (or let's keep TR=3)
    # If high=101, low=98, close=100, prev_close=97 -> TR = max(3, 4, 1) = 4.
    # To keep ATR = 3: prev_close = 97, high = 100, low = 97, close = 100 -> TR = 3
    daily_k.loc[n_days - 1, "high"] = 100.0
    daily_k.loc[n_days - 1, "low"] = 97.0
    daily_k.loc[n_days - 1, "close"] = 100.0
    daily_k.loc[n_days - 1, "volume"] = 2500.0

    _, rev, qf, inst, margin = _create_mock_datasets(
        n_days=n_days,
        fundamental_pass=True,
        chips_pass=True,
    )

    analysis = assemble_today_analysis("2330", daily_k, rev, qf, inst, margin)

    breakout_strat = next(s for s in analysis.strategies if s.strategy_name == params.STRATEGY_BREAKOUT_20D)
    assert breakout_strat.status == "進場"
    assert breakout_strat.action == "BUY"
    assert breakout_strat.entry_price == 100.0
    # Stop loss = 100 - 2 * 3 = 94, Take profit = 100 + 3 * 3 = 109
    assert breakout_strat.stop_loss == 94.0
    assert breakout_strat.take_profit == 109.0
    assert breakout_strat.max_holding_days == 20


def test_evaluation_date_and_disclaimer():
    """Verify evaluation date corresponds to last closed trading date and disclaimer is attached."""
    daily_k, rev, qf, inst, margin = _create_mock_datasets(
        last_close=100.0,
        fundamental_pass=True,
        chips_pass=True,
    )

    analysis = assemble_today_analysis("2330", daily_k, rev, qf, inst, margin)

    assert analysis.evaluation_date == daily_k["date"].iloc[-1]
    assert analysis.disclaimer == "僅供個人研究參考，非投資建議"
