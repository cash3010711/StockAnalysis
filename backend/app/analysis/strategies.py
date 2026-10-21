"""Implementation of the 5 technical trading strategies.

Each strategy provides:
1. Signal series generator: returns a boolean Series aligned with the input K-bars.
2. Watch trigger description: explains what price/volume level would trigger the strategy when watching.
"""

from typing import Dict, Tuple
import pandas as pd

from app.analysis import params
from app.analysis.indicators import compute_all_indicators


def evaluate_ma_pullback(df: pd.DataFrame) -> pd.Series:
    """Strategy 1: 均線多頭排列下拉回 20 日均線.

    Conditions on day t:
    1. Bullish MA alignment: MA5 > MA10 > MA20
    2. Pullback test: Low <= MA20 * 1.01 (tested or pulled back close to 20MA)
    3. Support held: Close >= MA20
    """
    signal = pd.Series(False, index=df.index)
    if df.empty or len(df) < params.MA_SLOW:
        return signal

    ma5 = df["ma5"]
    ma10 = df["ma10"]
    ma20 = df["ma20"]
    low = df["low"]
    close = df["close"]

    bullish = (ma5 > ma10) & (ma10 > ma20)
    pullback = low <= (ma20 * 1.01)
    support = close >= ma20

    signal = bullish & pullback & support
    return signal.fillna(False)


def evaluate_breakout_20d(df: pd.DataFrame) -> pd.Series:
    """Strategy 2: 帶量突破 20 日新高.

    Conditions on day t:
    1. Close > prior 20-day high (highest high of previous 20 trading days)
    2. Volume > 1.5 * 20-day average volume
    """
    signal = pd.Series(False, index=df.index)
    if df.empty or len(df) < params.BREAKOUT_WINDOW:
        return signal

    close = df["close"]
    volume = df["volume"]
    high_20_prev = df["high_20_prev"]
    vol_ma20 = df["vol_ma20"]

    price_breakout = close > high_20_prev
    vol_breakout = volume > (params.VOLUME_BREAKOUT_FACTOR * vol_ma20)

    signal = price_breakout & vol_breakout
    return signal.fillna(False)


def evaluate_macd_cross(df: pd.DataFrame) -> pd.Series:
    """Strategy 3: MACD 黃金交叉.

    Conditions on day t:
    DIF crosses above DEA: DIF[t-1] <= DEA[t-1] and DIF[t] > DEA[t]
    """
    signal = pd.Series(False, index=df.index)
    if df.empty or len(df) < params.MACD_SLOW:
        return signal

    dif = df["dif"]
    dea = df["dea"]

    dif_prev = dif.shift(1)
    dea_prev = dea.shift(1)

    golden_cross = (dif_prev <= dea_prev) & (dif > dea)
    return golden_cross.fillna(False)


def evaluate_kd_cross(df: pd.DataFrame) -> pd.Series:
    """Strategy 4: KD 低檔黃金交叉.

    Conditions on day t:
    1. Golden cross: K[t-1] <= D[t-1] and K[t] > D[t]
    2. Low level: K[t-1] <= 30 or K[t] <= 30
    """
    signal = pd.Series(False, index=df.index)
    if df.empty or len(df) < params.KD_PERIOD:
        return signal

    k = df["k"]
    d = df["d"]

    k_prev = k.shift(1)
    d_prev = d.shift(1)

    golden_cross = (k_prev <= d_prev) & (k > d)
    at_low_level = (k_prev <= params.KD_LOW_THRESHOLD) | (k <= params.KD_LOW_THRESHOLD)

    signal = golden_cross & at_low_level
    return signal.fillna(False)


def evaluate_bb_breakout(df: pd.DataFrame) -> pd.Series:
    """Strategy 5: 布林通道壓縮突破.

    Conditions on day t:
    1. Squeeze in prior 5 trading days (days t-5 to t-1):
       At least one day had bandwidth <= 20th percentile of rolling 120-day bandwidth distribution.
    2. Close > Bollinger upper band on day t
    3. Volume > 1.5 * 20-day average volume on day t
    """
    n = len(df)
    signal = pd.Series(False, index=df.index)
    if df.empty or n < params.BB_WINDOW:
        return signal

    close = df["close"]
    volume = df["volume"]
    upper = df["bb_upper"]
    vol_ma20 = df["vol_ma20"]
    width_pct = df["bb_width_pct"]

    # Check if any of the prior 5 days (t-5 to t-1) was squeezed (width_pct <= 0.20)
    # rolling(5) on shifted boolean series
    is_squeezed_day = (width_pct <= params.BB_SQUEEZE_PERCENTILE)
    had_squeeze_in_prior_5 = (
        is_squeezed_day.shift(1).rolling(window=params.BB_SQUEEZE_LOOKBACK_DAYS, min_periods=1).max() > 0
    )

    price_breakout = close > upper
    vol_breakout = volume > (params.BB_VOLUME_FACTOR * vol_ma20)

    signal = had_squeeze_in_prior_5 & price_breakout & vol_breakout
    return signal.fillna(False)


def get_strategy_trigger_description(strategy_name: str, df: pd.DataFrame, idx: int = -1) -> str:
    """Return human-readable trigger condition when a strategy is not yet triggered (觀望).

    Formulation adheres strictly to spec scenarios.
    """
    if df.empty:
        return "資料不足，無法評估觸發條件"

    row = df.iloc[idx]

    if strategy_name == params.STRATEGY_BREAKOUT_20D:
        high_prev = row.get("high_20_prev")
        if pd.notna(high_prev):
            # Format cleanly e.g. 152.5 or 152
            high_str = f"{high_prev:.1f}" if high_prev % 1 != 0 else f"{high_prev:.0f}"
            return f"收盤站上 {high_str} 且量大於 1.5 倍均量才觸發"
        return "收盤突破前 20 日最高價且量大於 1.5 倍均量才觸發"

    elif strategy_name == params.STRATEGY_BB_BREAKOUT:
        upper = row.get("bb_upper")
        # Check if squeezed
        width_pct = df["bb_width_pct"]
        is_squeezed_day = (width_pct <= params.BB_SQUEEZE_PERCENTILE)
        had_squeeze = False
        # Look back from idx-1 down to idx-5
        start_idx = max(0, (len(df) + idx if idx < 0 else idx) - params.BB_SQUEEZE_LOOKBACK_DAYS)
        end_idx = len(df) + idx if idx < 0 else idx
        if end_idx > start_idx:
            had_squeeze = bool(is_squeezed_day.iloc[start_idx:end_idx].any())

        if pd.notna(upper):
            upper_str = f"{upper:.1f}" if upper % 1 != 0 else f"{upper:.0f}"
            if had_squeeze:
                return f"收盤站上 {upper_str} 且量大於 1.5 倍均量才觸發"
            else:
                return f"待布林通道壓縮後，收盤站上 {upper_str} 且量大於 1.5 倍均量才觸發"
        return "待布林通道壓縮後帶量站上上軌才觸發"

    elif strategy_name == params.STRATEGY_MA_PULLBACK:
        ma20 = row.get("ma20")
        if pd.notna(ma20):
            ma_str = f"{ma20:.1f}" if ma20 % 1 != 0 else f"{ma20:.0f}"
            return f"收盤守穩 20MA ({ma_str}) 且均線多頭排列才觸發"
        return "均線多頭排列且拉回 20MA 守穩才觸發"

    elif strategy_name == params.STRATEGY_MACD_CROSS:
        return "待 MACD 出現黃金交叉 (DIF 向上突破 DEA) 才觸發"

    elif strategy_name == params.STRATEGY_KD_CROSS:
        return "待 KD 於低檔 (<=30) 出現黃金交叉才觸發"

    return "待技術面條件符合才觸發"


def evaluate_all_strategies(df_indicators: pd.DataFrame) -> Dict[str, pd.Series]:
    """Evaluate all 5 strategies on the indicator DataFrame, returning a dict of boolean Series."""
    df = df_indicators
    if "ma5" not in df.columns or "dif" not in df.columns or "k" not in df.columns:
        df = compute_all_indicators(df)

    return {
        params.STRATEGY_MA_PULLBACK: evaluate_ma_pullback(df),
        params.STRATEGY_BREAKOUT_20D: evaluate_breakout_20d(df),
        params.STRATEGY_MACD_CROSS: evaluate_macd_cross(df),
        params.STRATEGY_KD_CROSS: evaluate_kd_cross(df),
        params.STRATEGY_BB_BREAKOUT: evaluate_bb_breakout(df),
    }
