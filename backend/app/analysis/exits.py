"""Exit price level calculations and Taiwan stock tick-size rounding.

Taiwan Stock Exchange tick size rules:
- Price < 10: 0.01
- 10 <= Price < 50: 0.05
- 50 <= Price < 100: 0.10
- 100 <= Price < 500: 0.50
- 500 <= Price < 1000: 1.00
- Price >= 1000: 5.00
"""

from typing import Tuple
from app.analysis import params


def get_tick_size(price: float) -> float:
    """Return Taiwan stock tick size for a given price level."""
    if price < 10.0:
        return 0.01
    elif price < 50.0:
        return 0.05
    elif price < 100.0:
        return 0.10
    elif price < 500.0:
        return 0.50
    elif price < 1000.0:
        return 1.00
    else:
        return 5.00


def round_to_tick(price: float) -> float:
    """Round a price to the nearest valid Taiwan stock tick size."""
    if price <= 0:
        return 0.0
    tick = get_tick_size(price)
    # Round to nearest tick multiple
    rounded = round(price / tick) * tick
    return round(rounded, 2)


def calculate_exit_levels(
    entry_price: float,
    atr: float,
    stop_mult: float = params.STOP_LOSS_ATR_MULT,
    take_profit_mult: float = params.TAKE_PROFIT_ATR_MULT,
    max_holding_days: int = params.MAX_HOLDING_DAYS,
) -> Tuple[float, float, int]:
    """Calculate stop loss, take profit, and max holding days.

    stop_loss = round_to_tick(entry_price - 2 * ATR)
    take_profit = round_to_tick(entry_price + 3 * ATR)
    max_holding_days = 20
    """
    raw_stop = max(0.0, entry_price - stop_mult * atr)
    raw_profit = entry_price + take_profit_mult * atr

    stop_loss = round_to_tick(raw_stop)
    take_profit = round_to_tick(raw_profit)

    return stop_loss, take_profit, max_holding_days
