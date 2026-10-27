"""Unit tests for factor scoring module."""

import numpy as np
import pandas as pd
import pytest

from app.analysis.factor_scorer import (
    evaluate_stock_factor_score,
    score_to_decile,
)


def _make_daily_k(n: int = 150, base_price: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="B").strftime("%Y-%m-%d")
    prices = base_price + np.arange(n) * 0.2
    return pd.DataFrame({
        "stock_id": "TEST",
        "date": dates,
        "open": prices,
        "high": prices + 1.0,
        "low": prices - 1.0,
        "close": prices,
        "volume": [1000000.0] * n,
    })


def test_score_to_decile():
    """Verify decile thresholds and hit rate mapping."""
    decile, hit_rate, lift = score_to_decile(85.0)
    assert decile == 1
    assert hit_rate == 24.9
    assert lift == 2.00

    decile, hit_rate, lift = score_to_decile(60.0)
    assert decile == 2
    assert hit_rate == 19.7

    decile, hit_rate, lift = score_to_decile(2.0)
    assert decile == 10
    assert hit_rate == 9.9


def test_evaluate_stock_factor_score_high_performer():
    """Stock with strong breakout, RS, and market bull should score in top deciles."""
    df_k = _make_daily_k(150, 100.0)
    # Simulate breakout on last day: close breaks above prior 20-day high with 2x volume
    df_k.loc[149, "close"] = 150.0
    df_k.loc[149, "high"] = 151.0
    df_k.loc[149, "volume"] = 3000000.0

    res = evaluate_stock_factor_score(
        stock_id="TEST",
        daily_k=df_k,
        market_bull=True,
        custom_rs_pct=0.90,  # Top 10% RS
    )

    assert res.factor_score > 50.0
    assert "相對強度RS前20%" in res.triggered_factors
    assert "帶量突破20日新高" in res.triggered_factors
    assert "大盤多頭排列" in res.triggered_factors
    assert res.factor_decile in (1, 2)
    assert res.historical_hit_rate >= 19.0


def test_evaluate_stock_factor_score_low_performer():
    """Flat stock without any catalyst should score in bottom deciles."""
    df_k = _make_daily_k(60, 100.0)
    # Set flat price
    df_k["close"] = 100.0
    df_k["high"] = 100.5
    df_k["low"] = 99.5

    res = evaluate_stock_factor_score(
        stock_id="TEST",
        daily_k=df_k,
        market_bull=False,
        custom_rs_pct=0.20,
    )

    assert res.factor_score <= 10.0
    assert res.factor_decile >= 8
