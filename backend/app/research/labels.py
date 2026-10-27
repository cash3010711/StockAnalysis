"""Forward outcome label generation for stock factor research."""

from typing import Optional
import numpy as np
import pandas as pd

from app.research.config import StudyConfig


def compute_forward_labels(
    df_k: pd.DataFrame,
    config: Optional[StudyConfig] = None,
) -> pd.DataFrame:
    """Compute forward +15% / -7% / 20-day labels for a stock's daily K-bars.

    Args:
        df_k: DataFrame containing at least 'date', 'open', 'high', 'low', 'close'.
        config: StudyConfig containing thresholds. Defaults to standard StudyConfig.

    Returns:
        DataFrame with columns:
        ['date', 'forward_hit', 'forward_valid', 'exclude_reason']
    """
    cfg = config or StudyConfig()
    n = len(df_k)

    result = pd.DataFrame({
        "date": df_k["date"].astype(str).tolist(),
        "forward_hit": pd.Series(False, index=df_k.index, dtype=bool),
        "forward_valid": pd.Series(False, index=df_k.index, dtype=bool),
        "exclude_reason": pd.Series("", index=df_k.index, dtype=str),
    })

    if n < 2:
        if n == 1:
            result.loc[0, "exclude_reason"] = "insufficient_future_data"
        return result

    opens = df_k["open"].to_numpy(dtype=float)
    highs = df_k["high"].to_numpy(dtype=float)
    lows = df_k["low"].to_numpy(dtype=float)
    closes = df_k["close"].to_numpy(dtype=float)

    W = cfg.forward_window
    gain_mult = 1.0 + cfg.target_gain
    loss_mult = 1.0 - cfg.stop_loss
    gap_thresh = cfg.gap_threshold

    # Calculate overnight gaps between open[k] and close[k-1]
    gap_mask = np.zeros(n, dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = np.abs(opens[1:] / closes[:-1] - 1.0)
        gap_mask[1:] = np.nan_to_num(ratios, nan=0.0) > gap_thresh

    forward_hit = [False] * n
    forward_valid = [False] * n
    exclude_reasons = [""] * n

    for t in range(n):
        if t + 1 >= n:
            exclude_reasons[t] = "insufficient_future_data"
            continue

        entry_price = opens[t + 1]
        if entry_price <= 0 or np.isnan(entry_price):
            exclude_reasons[t] = "invalid_entry_price"
            continue

        target_price = entry_price * gain_mult
        stop_price = entry_price * loss_mult

        window_end = min(t + 1 + W, n)
        # Check gap / dividend in window [t + 1, window_end - 1]
        if np.any(gap_mask[t + 1 : window_end]):
            exclude_reasons[t] = "dividend_or_split_gap"
            continue

        # Look at intraday high and low
        sub_highs = highs[t + 1 : window_end]
        sub_lows = lows[t + 1 : window_end]

        hit_high_idx = np.where(sub_highs >= target_price)[0]
        hit_low_idx = np.where(sub_lows <= stop_price)[0]

        has_high = len(hit_high_idx) > 0
        has_low = len(hit_low_idx) > 0

        first_high = hit_high_idx[0] if has_high else 999999
        first_low = hit_low_idx[0] if has_low else 999999

        if has_high and not has_low:
            forward_hit[t] = True
            forward_valid[t] = True
        elif has_low and not has_high:
            forward_hit[t] = False
            forward_valid[t] = True
        elif has_high and has_low:
            if first_high < first_low:
                forward_hit[t] = True
                forward_valid[t] = True
            elif first_low < first_high:
                forward_hit[t] = False
                forward_valid[t] = True
            else:
                # Same day touched both: conservative rule -> stop loss takes precedence
                forward_hit[t] = False
                forward_valid[t] = True
        else:
            # Neither touched in the available window
            if t + W < n:
                forward_hit[t] = False
                forward_valid[t] = True
            else:
                forward_hit[t] = False
                forward_valid[t] = False
                exclude_reasons[t] = "insufficient_future_data"

    result["forward_hit"] = forward_hit
    result["forward_valid"] = forward_valid
    result["exclude_reason"] = exclude_reasons
    return result
