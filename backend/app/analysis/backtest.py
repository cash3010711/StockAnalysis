"""Backtest integration module for analysis."""
from typing import Any, Dict, List, Optional
import pandas as pd

from app.backtest.engine import Trade, run_backtest
from app.backtest.runner import (
    StockBacktestSummary,
    StrategyBacktestResult,
    run_all_backtests,
)
from app.backtest.stats import BacktestStats, EquityPoint, compute_stats

__all__ = [
    "Trade",
    "run_backtest",
    "StockBacktestSummary",
    "StrategyBacktestResult",
    "run_all_backtests",
    "BacktestStats",
    "EquityPoint",
    "compute_stats",
]
