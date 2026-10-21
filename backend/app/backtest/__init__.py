"""Backtest engine and statistics package."""

from app.backtest.engine import (
    Trade,
    calculate_trade_return,
    run_backtest,
)
from app.backtest.runner import (
    StockBacktestSummary,
    StrategyBacktestResult,
    run_all_backtests,
)
from app.backtest.stats import (
    BacktestStats,
    compute_stats,
)

__all__ = [
    "Trade",
    "calculate_trade_return",
    "run_backtest",
    "BacktestStats",
    "compute_stats",
    "StrategyBacktestResult",
    "StockBacktestSummary",
    "run_all_backtests",
]
