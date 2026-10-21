"""Unit tests for the 5 technical trading strategies."""

import numpy as np
import pandas as pd
import pytest

from app.analysis import params
from app.analysis.indicators import compute_all_indicators
from app.analysis.strategies import (
    evaluate_all_strategies,
    evaluate_bb_breakout,
    evaluate_breakout_20d,
    evaluate_kd_cross,
    evaluate_ma_pullback,
    evaluate_macd_cross,
    get_strategy_trigger_description,
)


def _build_base_df(n: int = 50, price: float = 100.0, volume: float = 1000.0) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({
        "date": dates,
        "open": [price] * n,
        "high": [price + 1.0] * n,
        "low": [price - 1.0] * n,
        "close": [price] * n,
        "volume": [volume] * n,
    })


def test_breakout_20d_scenarios():
    """Verify 帶量突破 20 日新高 matching spec scenarios."""
    df = _build_base_df(30, price=100.0, volume=1000.0)
    # Set day 0..28 highs to 100.0, with max high at 152.5 on day 15
    df.loc[15, "high"] = 152.5

    # Day 29: Spec scenario - Close 148 < 152.5
    df.loc[29, "close"] = 148.0
    df.loc[29, "volume"] = 2000.0
    df_ind = compute_all_indicators(df)

    signals = evaluate_breakout_20d(df_ind)
    assert not bool(signals.iloc[-1])
    desc = get_strategy_trigger_description(params.STRATEGY_BREAKOUT_20D, df_ind, idx=-1)
    assert "收盤站上 152.5 且量大於 1.5 倍均量才觸發" == desc

    # Day 29: Positive scenario - Close 153 > 152.5, Vol 1800 > 1.5 * 1000
    df.loc[29, "close"] = 153.0
    df.loc[29, "volume"] = 1800.0
    df_ind2 = compute_all_indicators(df)
    signals2 = evaluate_breakout_20d(df_ind2)
    assert bool(signals2.iloc[-1])

    # Day 29: Negative scenario - Price broke out, but volume insufficient (1200 <= 1500)
    df.loc[29, "close"] = 153.0
    df.loc[29, "volume"] = 1200.0
    df_ind3 = compute_all_indicators(df)
    signals3 = evaluate_breakout_20d(df_ind3)
    assert not bool(signals3.iloc[-1])


def test_bb_breakout_scenarios():
    """Verify 布林通道壓縮突破 matching spec scenarios."""
    df = _build_base_df(60, price=100.0, volume=1000.0)
    df_ind = compute_all_indicators(df)

    # Force artificial values to test exact scenario logic:
    # 3 days ago (idx -3) bandwidth was in lowest 20%
    df_ind["bb_width_pct"] = 0.50
    df_ind.iloc[-3, df_ind.columns.get_loc("bb_width_pct")] = 0.12  # 12th percentile!
    df_ind.iloc[-1, df_ind.columns.get_loc("close")] = 105.0
    df_ind.iloc[-1, df_ind.columns.get_loc("bb_upper")] = 101.3
    df_ind.iloc[-1, df_ind.columns.get_loc("vol_ma20")] = 1000.0
    df_ind.iloc[-1, df_ind.columns.get_loc("volume")] = 1800.0  # 1.8x volume

    # Positive scenario: compressed 3 days ago, closed above upper, volume > 1.5x
    signals = evaluate_bb_breakout(df_ind)
    assert bool(signals.iloc[-1])

    # Negative scenario 1: No compression in past 5 days (all width_pct > 0.20)
    df_ind_no_squeeze = df_ind.copy()
    df_ind_no_squeeze["bb_width_pct"] = 0.50
    signals_no_squeeze = evaluate_bb_breakout(df_ind_no_squeeze)
    assert not bool(signals_no_squeeze.iloc[-1])

    # Negative scenario 2: Spec scenario - Compressed in past 5 days, but close 98 < upper 101.3
    df_ind_watch = df_ind.copy()
    df_ind_watch.iloc[-1, df_ind_watch.columns.get_loc("close")] = 98.0
    df_ind_watch.iloc[-1, df_ind_watch.columns.get_loc("bb_upper")] = 101.3
    signals_watch = evaluate_bb_breakout(df_ind_watch)
    assert not bool(signals_watch.iloc[-1])
    desc_watch = get_strategy_trigger_description(params.STRATEGY_BB_BREAKOUT, df_ind_watch, idx=-1)
    assert desc_watch == "收盤站上 101.3 且量大於 1.5 倍均量才觸發"


def test_ma_pullback_scenarios():
    """Verify 均線多頭排列下拉回 20MA."""
    df = _build_base_df(30, price=100.0)
    df_ind = compute_all_indicators(df)

    # Positive: MA5 > MA10 > MA20, Low <= MA20 * 1.01, Close >= MA20
    df_ind.iloc[-1, df_ind.columns.get_loc("ma5")] = 105.0
    df_ind.iloc[-1, df_ind.columns.get_loc("ma10")] = 102.0
    df_ind.iloc[-1, df_ind.columns.get_loc("ma20")] = 100.0
    df_ind.iloc[-1, df_ind.columns.get_loc("low")] = 99.8  # dipped to touch/below 20MA
    df_ind.iloc[-1, df_ind.columns.get_loc("close")] = 100.5  # held above 20MA

    signals = evaluate_ma_pullback(df_ind)
    assert bool(signals.iloc[-1])

    # Negative: Broken below 20MA
    df_broken = df_ind.copy()
    df_broken.iloc[-1, df_broken.columns.get_loc("close")] = 98.0
    assert not bool(evaluate_ma_pullback(df_broken).iloc[-1])

    # Negative: Not in bullish alignment
    df_bear = df_ind.copy()
    df_bear.iloc[-1, df_bear.columns.get_loc("ma5")] = 95.0
    assert not bool(evaluate_ma_pullback(df_bear).iloc[-1])


def test_macd_cross_scenarios():
    """Verify MACD golden cross."""
    df = _build_base_df(35, price=100.0)
    df_ind = compute_all_indicators(df)

    # Positive: DIF crosses above DEA today
    df_ind.iloc[-2, df_ind.columns.get_loc("dif")] = -1.0
    df_ind.iloc[-2, df_ind.columns.get_loc("dea")] = 0.0
    df_ind.iloc[-1, df_ind.columns.get_loc("dif")] = 1.0
    df_ind.iloc[-1, df_ind.columns.get_loc("dea")] = 0.2

    signals = evaluate_macd_cross(df_ind)
    assert bool(signals.iloc[-1])

    # Negative: Already crossed yesterday and still above today (no new cross)
    df_ind.iloc[-2, df_ind.columns.get_loc("dif")] = 1.5
    df_ind.iloc[-2, df_ind.columns.get_loc("dea")] = 0.5
    signals_no_cross = evaluate_macd_cross(df_ind)
    assert not bool(signals_no_cross.iloc[-1])


def test_kd_cross_scenarios():
    """Verify KD low golden cross."""
    df = _build_base_df(30, price=100.0)
    df_ind = compute_all_indicators(df)

    # Positive: K crosses above D at low level (<=30)
    df_ind.iloc[-2, df_ind.columns.get_loc("k")] = 20.0
    df_ind.iloc[-2, df_ind.columns.get_loc("d")] = 25.0
    df_ind.iloc[-1, df_ind.columns.get_loc("k")] = 28.0
    df_ind.iloc[-1, df_ind.columns.get_loc("d")] = 26.0

    signals = evaluate_kd_cross(df_ind)
    assert bool(signals.iloc[-1])

    # Negative: Golden cross at high level (K=65, D=62)
    df_high = df_ind.copy()
    df_high.iloc[-2, df_high.columns.get_loc("k")] = 58.0
    df_high.iloc[-2, df_high.columns.get_loc("d")] = 60.0
    df_high.iloc[-1, df_high.columns.get_loc("k")] = 65.0
    df_high.iloc[-1, df_high.columns.get_loc("d")] = 62.0
    assert not bool(evaluate_kd_cross(df_high).iloc[-1])


def test_evaluate_all_strategies_integration():
    """Verify evaluate_all_strategies produces results for all 5 strategies."""
    df = _build_base_df(30, price=100.0)
    all_res = evaluate_all_strategies(df)
    assert len(all_res) == 5
    for name in params.ALL_STRATEGIES:
        assert name in all_res
        assert len(all_res[name]) == len(df)
