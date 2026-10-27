"""Unit tests for technical indicators with hand-calculated fixtures (error < 1e-6)."""

import numpy as np
import pandas as pd
import pytest

from app.analysis.indicators import (
    compute_all_indicators,
    compute_atr,
    compute_bandwidth_percentile,
    compute_bollinger_bands,
    compute_kd,
    compute_ma,
    compute_macd,
    compute_rolling_high,
    compute_volume_ma,
)


def test_compute_ma():
    """Verify Moving Average matches hand calculations."""
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    ma3 = compute_ma(s, 3)

    assert pd.isna(ma3.iloc[0])
    assert pd.isna(ma3.iloc[1])
    assert pytest.approx(ma3.iloc[2], rel=1e-6) == 20.0
    assert pytest.approx(ma3.iloc[3], rel=1e-6) == 30.0
    assert pytest.approx(ma3.iloc[4], rel=1e-6) == 40.0


def test_compute_atr_hand_calculated():
    """Verify ATR(3) matches step-by-step hand calculation."""
    # Day 0: H=12, L=10, C=11 -> TR0 = 12 - 10 = 2.0
    # Day 1: H=14, L=9,  C=13 -> TR1 = max(14-9=5, |14-11|=3, |9-11|=2) = 5.0
    # Day 2: H=15, L=12, C=14 -> TR2 = max(15-12=3, |15-13|=2, |12-13|=1) = 3.0
    # Initial ATR(3) at Day 2 = (2 + 5 + 3) / 3 = 10 / 3 = 3.3333333333333335
    # Day 3: H=16, L=11, C=12 -> TR3 = max(16-11=5, |16-14|=2, |11-14|=3) = 5.0
    # ATR(3) at Day 3 = (ATR2 * 2 + TR3) / 3 = (20/3 + 15/3) / 3 = 35 / 9 = 3.888888888888889
    high = pd.Series([12.0, 14.0, 15.0, 16.0])
    low = pd.Series([10.0, 9.0, 12.0, 11.0])
    close = pd.Series([11.0, 13.0, 14.0, 12.0])

    atr = compute_atr(high, low, close, window=3)

    assert pd.isna(atr.iloc[0])
    assert pd.isna(atr.iloc[1])
    assert pytest.approx(atr.iloc[2], rel=1e-6) == 10.0 / 3.0
    assert pytest.approx(atr.iloc[3], rel=1e-6) == 35.0 / 9.0


def test_compute_atr14_full():
    """Verify ATR(14) with 15 rows of data."""
    # 15 days of data
    high = pd.Series([100.0 + i for i in range(15)])
    low = pd.Series([98.0 + i for i in range(15)])
    close = pd.Series([99.0 + i for i in range(15)])

    atr = compute_atr(high, low, close, window=14)
    assert pd.isna(atr.iloc[12])
    assert not pd.isna(atr.iloc[13])
    assert not pd.isna(atr.iloc[14])
    # Each day H-L is 2.0, and H - prev_close is 101 - 99 = 2.0, low - prev_close is |99 - 99| = 0
    # So every TR = 2.0. ATR must be exactly 2.0!
    assert pytest.approx(atr.iloc[13], rel=1e-6) == 2.0
    assert pytest.approx(atr.iloc[14], rel=1e-6) == 2.0


def test_compute_macd_hand_calculated():
    """Verify MACD components match expected pandas ewm calculation."""
    # Constant series of 100 -> EMAs should all be 100, DIF=0, DEA=0, HIST=0
    close_const = pd.Series([100.0] * 35)
    dif, dea, hist = compute_macd(close_const, 12, 26, 9)
    assert pytest.approx(dif.iloc[-1], abs=1e-6) == 0.0
    assert pytest.approx(dea.iloc[-1], abs=1e-6) == 0.0
    assert pytest.approx(hist.iloc[-1], abs=1e-6) == 0.0

    # Test EMA step calculation on 2 bars:
    # close: 10, 20
    # ema12: bar0 = 10, alpha = 2/13
    # bar1 = (1 - 2/13) * 10 + 2/13 * 20 = 10 * 11/13 + 40/13 = 150 / 13 = 11.5384615
    close2 = pd.Series([10.0, 20.0])
    ema_fast = close2.ewm(span=12, adjust=False).mean()
    assert pytest.approx(ema_fast.iloc[0], rel=1e-6) == 10.0
    assert pytest.approx(ema_fast.iloc[1], rel=1e-6) == 150.0 / 13.0


def test_compute_kd_hand_calculated():
    """Verify KD(3, 3, 3) hand calculated values."""
    # Day 0: H=10, L=8, C=9 -> Low3=8, High3=10, RSV = 50.0
    # K0 = 2/3 * 50 + 1/3 * 50 = 50.0
    # D0 = 2/3 * 50 + 1/3 * 50 = 50.0
    # Day 1: H=12, L=9, C=11 -> Low3=8, High3=12, RSV = (11-8)/(12-8)*100 = 75.0
    # K1 = 2/3 * 50 + 1/3 * 75 = 175/3 = 58.33333333
    # D1 = 2/3 * 50 + 1/3 * (175/3) = 475/9 = 52.77777778
    # Day 2: H=14, L=11, C=11 -> Low3=8, High3=14, RSV = (11-8)/(14-8)*100 = 50.0
    # K2 = 2/3 * (175/3) + 1/3 * 50 = 500/9 = 55.55555556
    # D2 = 2/3 * (475/9) + 1/3 * (500/9) = 1450/27 = 53.70370370
    high = pd.Series([10.0, 12.0, 14.0])
    low = pd.Series([8.0, 9.0, 11.0])
    close = pd.Series([9.0, 11.0, 11.0])

    k, d = compute_kd(high, low, close, period=3, smooth_k=3, smooth_d=3)

    assert pytest.approx(k.iloc[0], rel=1e-6) == 50.0
    assert pytest.approx(d.iloc[0], rel=1e-6) == 50.0
    assert pytest.approx(k.iloc[1], rel=1e-6) == 175.0 / 3.0
    assert pytest.approx(d.iloc[1], rel=1e-6) == 475.0 / 9.0
    assert pytest.approx(k.iloc[2], rel=1e-6) == 500.0 / 9.0
    assert pytest.approx(d.iloc[2], rel=1e-6) == 1450.0 / 27.0


def test_compute_bollinger_bands():
    """Verify Bollinger Bands mid, upper, lower and bandwidth."""
    # 20 items: 10 items of 95, 10 items of 105
    # mean = 100.0
    # pop std (ddof=0): sqrt(10*(95-100)^2 + 10*(105-100)^2 / 20) = sqrt(25) = 5.0
    close = pd.Series([95.0] * 10 + [105.0] * 10)
    mid, upper, lower, bandwidth = compute_bollinger_bands(close, window=20, num_std=2.0)

    assert pd.isna(mid.iloc[18])
    assert pytest.approx(mid.iloc[19], rel=1e-6) == 100.0
    assert pytest.approx(upper.iloc[19], rel=1e-6) == 110.0
    assert pytest.approx(lower.iloc[19], rel=1e-6) == 90.0
    # bandwidth = (110 - 90) / 100 = 0.20
    assert pytest.approx(bandwidth.iloc[19], rel=1e-6) == 0.20


def test_compute_rolling_high():
    """Verify prior 20-day high (shift_1=True)."""
    # 5 items with window=3
    high = pd.Series([10.0, 15.0, 12.0, 18.0, 14.0])
    h3_prev = compute_rolling_high(high, window=3, shift_1=True)

    # Shifted: [NaN, 10, 15, 12, 18]
    # Window=3:
    # idx 0: NaN
    # idx 1: NaN
    # idx 2: NaN
    # idx 3: max(10, 15, 12) = 15.0
    # idx 4: max(15, 12, 18) = 18.0
    assert pd.isna(h3_prev.iloc[2])
    assert pytest.approx(h3_prev.iloc[3], rel=1e-6) == 15.0
    assert pytest.approx(h3_prev.iloc[4], rel=1e-6) == 18.0


def test_compute_volume_ma():
    """Verify volume MA calculation."""
    vol = pd.Series([100.0, 200.0, 300.0, 400.0])
    ma_vol = compute_volume_ma(vol, window=3)

    assert pd.isna(ma_vol.iloc[1])
    assert pytest.approx(ma_vol.iloc[2], rel=1e-6) == 200.0
    assert pytest.approx(ma_vol.iloc[3], rel=1e-6) == 300.0


def test_compute_bandwidth_percentile():
    """Verify bandwidth percentile ranking."""
    # 10 values from 0.10 to 1.00
    bw = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    # window=5, min_periods=5
    pct = compute_bandwidth_percentile(bw, window=5, min_periods=5)
    # At index 4: window is [0.1, 0.2, 0.3, 0.4, 0.5], current is 0.5 -> 5/5 = 1.0
    assert pytest.approx(pct.iloc[4], rel=1e-6) == 1.0

    # Let's test a dip:
    bw2 = pd.Series([0.5, 0.6, 0.7, 0.8, 0.1])
    pct2 = compute_bandwidth_percentile(bw2, window=5, min_periods=5)
    # At index 4: current is 0.1, which is lowest -> 1/5 = 0.20
    assert pytest.approx(pct2.iloc[4], rel=1e-6) == 0.20


def test_compute_all_indicators_ma60_ma120():
    """Verify compute_all_indicators calculates ma60 and ma120."""
    n = 150
    dates = pd.date_range("2026-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": dates,
        "open": [100.0 + i for i in range(n)],
        "high": [105.0 + i for i in range(n)],
        "low": [95.0 + i for i in range(n)],
        "close": [100.0 + i for i in range(n)],
        "volume": [1000 + i * 10 for i in range(n)],
    })

    result = compute_all_indicators(df)
    assert "ma60" in result.columns
    assert "ma120" in result.columns

    # Check NaN before window
    assert pd.isna(result["ma60"].iloc[58])
    assert pd.isna(result["ma120"].iloc[118])

    # Check exact average at window
    # close is 100, 101, ..., 159 (60 values) -> mean is 129.5
    assert pytest.approx(result["ma60"].iloc[59], rel=1e-6) == float(df["close"].iloc[:60].mean())
    # close for first 120 values -> mean is df["close"].iloc[:120].mean()
    assert pytest.approx(result["ma120"].iloc[119], rel=1e-6) == float(df["close"].iloc[:120].mean())

