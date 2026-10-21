"""Statistical calculations for backtest results.

Computes metrics:
- Trade count, win count, loss count
- Win rate (None if total_trades == 0)
- Average net return & expected value (per trade)
- Average holding days
- Max drawdown (computed on trade-by-trade cumulative equity)
- Insufficient sample warning flag (trades < 20)
- Status display text (e.g. '無交易', '樣本不足，參考性低')
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from app.analysis import params
from app.backtest.engine import Trade


@dataclass
class BacktestStats:
    """Summary statistics for backtest performance."""

    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: Optional[float]
    win_rate_pct: Optional[float]
    avg_return: Optional[float]
    avg_return_pct: Optional[float]
    expected_value: Optional[float]
    expected_value_pct: Optional[float]
    avg_holding_days: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_pct: Optional[float]
    insufficient_sample: bool
    has_trades: bool
    status_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return asdict(self)


def compute_stats(
    trades: List[Trade],
    min_sample_size: int = params.MIN_SAMPLE_SIZE,
) -> BacktestStats:
    """Compute summary statistics for a list of trades.

    Args:
        trades: List of completed Trade objects.
        min_sample_size: Threshold for sample size warning (default 20).

    Returns:
        BacktestStats object.
    """
    total_trades = len(trades)

    if total_trades == 0:
        return BacktestStats(
            total_trades=0,
            win_trades=0,
            loss_trades=0,
            win_rate=None,
            win_rate_pct=None,
            avg_return=None,
            avg_return_pct=None,
            expected_value=None,
            expected_value_pct=None,
            avg_holding_days=None,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            insufficient_sample=True,
            has_trades=False,
            status_text="無交易",
        )

    win_trades = sum(1 for t in trades if t.is_win)
    loss_trades = total_trades - win_trades
    win_rate = win_trades / total_trades
    win_rate_pct = round(win_rate * 100, 2)

    returns = [t.net_return for t in trades]
    avg_return = sum(returns) / total_trades
    avg_return_pct = round(avg_return * 100, 2)
    expected_value = avg_return
    expected_value_pct = avg_return_pct

    holding_days_list = [t.holding_days for t in trades]
    avg_holding_days = round(sum(holding_days_list) / total_trades, 1)

    # Calculate max drawdown on trade-by-trade compounding equity curve
    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        equity *= 1.0 + r
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

    max_drawdown = round(max_dd, 4)
    max_drawdown_pct = round(max_dd * 100, 2)

    insufficient_sample = total_trades < min_sample_size
    status_text = "樣本不足，參考性低" if insufficient_sample else None

    return BacktestStats(
        total_trades=total_trades,
        win_trades=win_trades,
        loss_trades=loss_trades,
        win_rate=win_rate,
        win_rate_pct=win_rate_pct,
        avg_return=avg_return,
        avg_return_pct=avg_return_pct,
        expected_value=expected_value,
        expected_value_pct=expected_value_pct,
        avg_holding_days=avg_holding_days,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        insufficient_sample=insufficient_sample,
        has_trades=True,
        status_text=status_text,
    )
