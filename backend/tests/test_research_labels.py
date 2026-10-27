"""Unit tests for forward label computation."""

import numpy as np
import pandas as pd
import pytest

from app.research.config import StudyConfig
from app.research.labels import compute_forward_labels


def _make_sample_df(n: int, base_price: float = 100.0) -> pd.DataFrame:
    """Helper to generate a base flat dataframe of n days."""
    dates = pd.date_range("2024-01-01", periods=n, freq="B").strftime("%Y-%m-%d")
    return pd.DataFrame({
        "date": dates,
        "open": [base_price] * n,
        "high": [base_price * 1.02] * n,
        "low": [base_price * 0.98] * n,
        "close": [base_price] * n,
        "volume": [1000000.0] * n,
    })


def test_first_rises_then_falls():
    """Scenario: 先漲到 +15% 才回檔 -> 命中 (forward_hit=True, forward_valid=True)."""
    df = _make_sample_df(30, 100.0)
    # Entry on day 1 is open=100.
    # Day 8 high touches 115.5 (+15.5%)
    df.loc[8, "high"] = 115.5
    # Day 12 low drops to 90 (-10%)
    df.loc[12, "low"] = 90.0

    res = compute_forward_labels(df)
    assert bool(res.loc[0, "forward_valid"]) is True
    assert bool(res.loc[0, "forward_hit"]) is True
    assert res.loc[0, "exclude_reason"] == ""


def test_first_drops_below_stop_loss():
    """Scenario: 先跌破 -7% -> 未命中 (forward_hit=False, forward_valid=True)."""
    df = _make_sample_df(30, 100.0)
    # Entry on day 1 is open=100.
    # Day 3 low touches 92.5 (-7.5%)
    df.loc[3, "low"] = 92.5
    # Day 10 high reaches 120 (+20%)
    df.loc[10, "high"] = 120.0

    res = compute_forward_labels(df)
    assert bool(res.loc[0, "forward_valid"]) is True
    assert bool(res.loc[0, "forward_hit"]) is False
    assert res.loc[0, "exclude_reason"] == ""


def test_same_day_touch_both():
    """Scenario: 同一天同時觸及 +15% 與 -7% -> 保守判定未命中."""
    df = _make_sample_df(30, 100.0)
    # Entry on day 1 is open=100.
    # Day 5 high = 116, low = 92
    df.loc[5, "high"] = 116.0
    df.loc[5, "low"] = 92.0

    res = compute_forward_labels(df)
    assert bool(res.loc[0, "forward_valid"]) is True
    assert bool(res.loc[0, "forward_hit"]) is False
    assert res.loc[0, "exclude_reason"] == ""


def test_insufficient_future_data_at_tail():
    """Scenario: 資料尾端不足 20 日且未觸發 -> forward_valid=False."""
    df = _make_sample_df(15, 100.0)  # Only 15 days total
    # For day 0, only 14 days of future data available, flat price
    res = compute_forward_labels(df)
    assert bool(res.loc[0, "forward_valid"]) is False
    assert bool(res.loc[0, "forward_hit"]) is False
    assert res.loc[0, "exclude_reason"] == "insufficient_future_data"

    # Very last day
    assert bool(res.loc[14, "forward_valid"]) is False
    assert res.loc[14, "exclude_reason"] == "insufficient_future_data"


def test_dividend_or_split_gap_exclusion():
    """Scenario: 視窗內出現除權息/分割跳空缺口 (>10.5%) -> 排除."""
    df = _make_sample_df(30, 100.0)
    # Day 5 open is 75 (down 25% from day 4 close 100)
    df.loc[5, "open"] = 75.0
    df.loc[5, "high"] = 76.0
    df.loc[5, "low"] = 74.0
    df.loc[5, "close"] = 75.0

    res = compute_forward_labels(df)
    assert bool(res.loc[0, "forward_valid"]) is False
    assert res.loc[0, "exclude_reason"] == "dividend_or_split_gap"
