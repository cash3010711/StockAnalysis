"""Technical indicators calculation for Taiwan stock analysis.

All indicators are pure functions operating on pandas Series / DataFrames.
"""

from typing import Tuple
import numpy as np
import pandas as pd


def compute_ma(series: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average (SMA)."""
    return series.rolling(window=window).mean()


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """Compute Average True Range (ATR) using Wilder's smoothing method.

    TR_t = max(High_t - Low_t, abs(High_t - Close_{t-1}), abs(Low_t - Close_{t-1}))
    First ATR is the SMA of the first `window` TR values.
    Subsequent ATR_t = (ATR_{t-1} * (window - 1) + TR_t) / window.
    """
    n = len(close)
    if n == 0:
        return pd.Series(dtype=float)

    prev_close = close.shift(1)
    # TR calculation
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # First bar TR is high - low
    tr.iloc[0] = high.iloc[0] - low.iloc[0]

    atr = pd.Series(index=close.index, dtype=float)
    if n < window:
        return atr

    # Initial SMA of TR
    atr.iloc[window - 1] = tr.iloc[:window].mean()
    for i in range(window, n):
        atr.iloc[i] = (atr.iloc[i - 1] * (window - 1) + tr.iloc[i]) / window

    return atr


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD (DIF, DEA, MACD Histogram).

    Fast EMA: span = 12
    Slow EMA: span = 26
    DIF: Fast EMA - Slow EMA
    DEA: 9-span EMA of DIF
    MACD Hist: DIF - DEA
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = dif - dea
    return dif, dea, macd_hist


def compute_kd(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 9,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> Tuple[pd.Series, pd.Series]:
    """Compute Taiwan standard Stochastic KD(9, 3, 3).

    RSV = (Close - MinLow_9) / (MaxHigh_9 - MinLow_9) * 100
    K_t = 2/3 * K_{t-1} + 1/3 * RSV_t
    D_t = 2/3 * D_{t-1} + 1/3 * K_t
    Initial values: K_0 = 50, D_0 = 50
    """
    n = len(close)
    if n == 0:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    lowest_low = low.rolling(window=period, min_periods=1).min()
    highest_high = high.rolling(window=period, min_periods=1).max()

    denom = highest_high - lowest_low
    rsv = pd.Series(50.0, index=close.index, dtype=float)
    valid_denom = denom > 1e-9
    rsv[valid_denom] = (close[valid_denom] - lowest_low[valid_denom]) / denom[valid_denom] * 100.0

    k = pd.Series(index=close.index, dtype=float)
    d = pd.Series(index=close.index, dtype=float)

    alpha_k = 1.0 / smooth_k
    alpha_d = 1.0 / smooth_d

    curr_k = 50.0
    curr_d = 50.0
    for i in range(n):
        curr_k = (1.0 - alpha_k) * curr_k + alpha_k * rsv.iloc[i]
        curr_d = (1.0 - alpha_d) * curr_d + alpha_d * curr_k
        k.iloc[i] = curr_k
        d.iloc[i] = curr_d

    return k, d


def compute_bollinger_bands(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger Bands (Mid, Upper, Lower, Bandwidth).

    Mid: 20 SMA
    Upper: Mid + 2 * Std (population std, ddof=0)
    Lower: Mid - 2 * Std
    Bandwidth: (Upper - Lower) / Mid
    """
    mid = close.rolling(window=window).mean()
    std = close.rolling(window=window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    bandwidth = (upper - lower) / mid
    return mid, upper, lower, bandwidth


def compute_bandwidth_percentile(
    bandwidth: pd.Series,
    window: int = 120,
    min_periods: int = 20,
) -> pd.Series:
    """Compute rolling percentile rank (0.0 ~ 1.0) of bandwidth within the past `window` days.

    A value <= 0.20 indicates bandwidth is within the lowest 20% of the past 120 days.
    """
    def _pct_rank(w: np.ndarray) -> float:
        # What fraction of items in window w are <= current day value w[-1]
        valid = w[~np.isnan(w)]
        if len(valid) == 0:
            return np.nan
        return float(np.mean(valid <= valid[-1]))

    return bandwidth.rolling(window=window, min_periods=min_periods).apply(_pct_rank, raw=True)


def compute_rolling_high(
    high: pd.Series,
    window: int = 20,
    shift_1: bool = True,
) -> pd.Series:
    """Compute rolling highest high.

    If shift_1=True, returns highest high of the `window` days BEFORE today (i.e. T-window to T-1).
    """
    if shift_1:
        return high.shift(1).rolling(window=window).max()
    return high.rolling(window=window).max()


def compute_volume_ma(volume: pd.Series, window: int = 20) -> pd.Series:
    """Compute Simple Moving Average of Volume."""
    return volume.rolling(window=window).mean()


def compute_all_indicators(df_k: pd.DataFrame) -> pd.DataFrame:
    """Compute all indicators and return a copy of df_k with indicator columns attached."""
    df = df_k.copy()
    if df.empty:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Moving averages
    df["ma5"] = compute_ma(close, 5)
    df["ma10"] = compute_ma(close, 10)
    df["ma20"] = compute_ma(close, 20)
    df["ma60"] = compute_ma(close, 60)

    # ATR
    df["atr14"] = compute_atr(high, low, close, 14)

    # MACD
    dif, dea, macd_hist = compute_macd(close, 12, 26, 9)
    df["dif"] = dif
    df["dea"] = dea
    df["macd_hist"] = macd_hist

    # KD
    k, d = compute_kd(high, low, close, 9, 3, 3)
    df["k"] = k
    df["d"] = d

    # Bollinger Bands
    bb_mid, bb_upper, bb_lower, bb_width = compute_bollinger_bands(close, 20, 2.0)
    df["bb_mid"] = bb_mid
    df["bb_upper"] = bb_upper
    df["bb_lower"] = bb_lower
    df["bb_width"] = bb_width
    df["bb_width_pct"] = compute_bandwidth_percentile(bb_width, window=120, min_periods=20)

    # 20-day high (prior 20 days)
    df["high_20_prev"] = compute_rolling_high(high, 20, shift_1=True)
    df["vol_ma20"] = compute_volume_ma(volume, 20)

    return df
