"""Backtest simulation engine for Taiwan stock trading strategies.

Implements a daily state machine:
- Enters at next day's open after a close signal.
- Non-overlapping positions: new signals during active positions are ignored.
- Exit levels fixed at entry using signal day's ATR:
  * Stop loss = round_to_tick(entry_price - 2 * ATR)
  * Take profit = round_to_tick(entry_price + 3 * ATR)
  * Max holding days = 20
- Exit rules:
  1. Gap down below stop loss at open: exit at open, is_win = False.
  2. Both stop loss and take profit touched in same day: exit at stop loss, is_win = False.
  3. Low touches stop loss: exit at stop loss, is_win = False.
  4. High touches take profit: exit at take profit, is_win = True.
  5. Held for 20 trading days: exit at close, is_win = (net_return > 0).
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import pandas as pd

from app.analysis import params
from app.analysis.exits import calculate_exit_levels


def calculate_trade_return(
    entry_price: float,
    exit_price: float,
    fee_rate: float = params.TRANSACTION_FEE_RATE,
    tax_rate: float = params.TRANSACTION_TAX_RATE,
) -> tuple[float, float]:
    """Calculate gross and net return for a single trade.

    gross_return = (exit_price - entry_price) / entry_price
    net_return = (exit_price * (1 - fee - tax) - entry_price * (1 + fee)) / entry_price
    """
    if entry_price <= 0:
        return 0.0, 0.0

    gross_return = (exit_price - entry_price) / entry_price
    buy_cost = entry_price * (1.0 + fee_rate)
    sell_proceeds = exit_price * (1.0 - fee_rate - tax_rate)
    net_return = (sell_proceeds - buy_cost) / entry_price
    return gross_return, net_return


@dataclass
class Trade:
    """Record of a completed trade in backtesting."""

    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    stop_loss: float
    take_profit: float
    holding_days: int
    gross_return: float
    net_return: float
    exit_reason: str  # "stop_loss", "stop_loss_gap", "take_profit", "max_holding_days"
    is_win: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert trade record to dictionary."""
        return asdict(self)


def run_backtest(
    df: pd.DataFrame,
    signal_mask: pd.Series,
    fee_rate: float = params.TRANSACTION_FEE_RATE,
    tax_rate: float = params.TRANSACTION_TAX_RATE,
    max_holding_days: int = params.MAX_HOLDING_DAYS,
) -> List[Trade]:
    """Run daily state-machine backtest over historical price data.

    Args:
        df: DataFrame with columns 'date', 'open', 'high', 'low', 'close', and 'atr14'.
        signal_mask: Boolean Series aligned with df indicating buy signal at day's close.
        fee_rate: Commission fee rate (each side).
        tax_rate: Transaction tax rate (sell side).
        max_holding_days: Maximum holding period in trading days.

    Returns:
        List of completed Trade objects.
    """
    if df.empty or len(df) == 0:
        return []

    trades: List[Trade] = []
    n = len(df)

    active_position: Optional[Dict[str, Any]] = None
    pending_entry_atr: Optional[float] = None

    dates = df["date"].astype(str).values
    opens = df["open"].astype(float).values
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    closes = df["close"].astype(float).values
    atrs = df["atr14"].astype(float).values if "atr14" in df.columns else [0.0] * n
    signals = signal_mask.values

    for i in range(n):
        curr_date = dates[i]
        curr_open = opens[i]
        curr_high = highs[i]
        curr_low = lows[i]
        curr_close = closes[i]

        # 1. Check pending entry from previous day's signal
        if active_position is None and pending_entry_atr is not None:
            entry_price = curr_open
            atr_val = pending_entry_atr
            stop_loss, take_profit, _ = calculate_exit_levels(
                entry_price=entry_price,
                atr=atr_val,
                max_holding_days=max_holding_days,
            )
            active_position = {
                "entry_date": curr_date,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "holding_days": 1,
            }
            pending_entry_atr = None

        # 2. Process active position
        if active_position is not None:
            stop_loss = active_position["stop_loss"]
            take_profit = active_position["take_profit"]
            entry_price = active_position["entry_price"]
            entry_date = active_position["entry_date"]
            holding_days = active_position["holding_days"]

            trade_exited = False
            exit_price = 0.0
            exit_reason = ""
            is_win = False

            # Rule A: Gap down at open below stop loss (for days after entry day)
            if holding_days > 1 and curr_open <= stop_loss:
                trade_exited = True
                exit_price = curr_open
                exit_reason = "stop_loss_gap"
                is_win = False

            # Rule B: Intraday price check
            if not trade_exited:
                hit_stop = curr_low <= stop_loss
                hit_take = curr_high >= take_profit

                if hit_stop and hit_take:
                    # Same day hit both -> conservative rule: stop loss
                    trade_exited = True
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                    is_win = False
                elif hit_stop:
                    trade_exited = True
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                    is_win = False
                elif hit_take:
                    trade_exited = True
                    exit_price = take_profit
                    exit_reason = "take_profit"
                    is_win = True
                elif holding_days >= max_holding_days:
                    # Rule C: Max holding period reached -> exit at today's close
                    trade_exited = True
                    exit_price = curr_close
                    exit_reason = "max_holding_days"
                    gross_ret, net_ret = calculate_trade_return(
                        entry_price=entry_price,
                        exit_price=exit_price,
                        fee_rate=fee_rate,
                        tax_rate=tax_rate,
                    )
                    is_win = net_ret > 0.0

            if trade_exited:
                gross_ret, net_ret = calculate_trade_return(
                    entry_price=entry_price,
                    exit_price=exit_price,
                    fee_rate=fee_rate,
                    tax_rate=tax_rate,
                )
                # For stop_loss / stop_loss_gap, is_win is False
                # For take_profit, is_win is True
                # For max_holding_days, is_win is (net_ret > 0.0)
                trades.append(
                    Trade(
                        entry_date=str(entry_date),
                        entry_price=float(entry_price),
                        exit_date=str(curr_date),
                        exit_price=float(exit_price),
                        stop_loss=float(stop_loss),
                        take_profit=float(take_profit),
                        holding_days=int(holding_days),
                        gross_return=float(gross_ret),
                        net_return=float(net_ret),
                        exit_reason=str(exit_reason),
                        is_win=bool(is_win),
                    )
                )
                active_position = None
            else:
                # Still holding into next day
                active_position["holding_days"] += 1

        # 3. Check for new signal at close of day i
        # Only accept new signal if flat (active_position is None)
        if active_position is None:
            if bool(signals[i]):
                atr_candidate = atrs[i]
                pending_entry_atr = atr_candidate if pd.notna(atr_candidate) else 0.0
        else:
            # Holding position: ignore any new signals
            pass

    return trades
