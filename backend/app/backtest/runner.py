"""Runner for executing strategy backtests with three-layer and tech-only masks."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd

from app.analysis import params
from app.analysis.indicators import compute_all_indicators
from app.analysis.layers import (
    evaluate_chips_series,
    evaluate_fundamentals_series,
)
from app.analysis.strategies import evaluate_all_strategies
from app.backtest.engine import Trade, run_backtest
from app.backtest.stats import BacktestStats, compute_stats


@dataclass
class StrategyBacktestResult:
    """Backtest comparison results for a single strategy."""

    strategy_name: str
    can_backtest: bool
    message: Optional[str] = None
    three_layer: Optional[BacktestStats] = None
    tech_only: Optional[BacktestStats] = None
    three_layer_trades: List[Trade] = field(default_factory=list)
    tech_only_trades: List[Trade] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy backtest result to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "can_backtest": self.can_backtest,
            "message": self.message,
            "three_layer": self.three_layer.to_dict() if self.three_layer else None,
            "tech_only": self.tech_only.to_dict() if self.tech_only else None,
            "three_layer_trades": [t.to_dict() for t in self.three_layer_trades],
            "tech_only_trades": [t.to_dict() for t in self.tech_only_trades],
        }


@dataclass
class StockBacktestSummary:
    """Summary of backtest results across all strategies for a stock."""

    stock_id: str
    evaluation_date: str
    can_backtest: bool
    message: Optional[str] = None
    results: List[StrategyBacktestResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "stock_id": self.stock_id,
            "evaluation_date": self.evaluation_date,
            "can_backtest": self.can_backtest,
            "message": self.message,
            "results": [r.to_dict() for r in self.results],
        }


def run_all_backtests(
    stock_id: str,
    daily_k: pd.DataFrame,
    monthly_revenue: pd.DataFrame,
    quarterly_financials: pd.DataFrame,
    institutional_investors: pd.DataFrame,
    margin_short: pd.DataFrame,
    strategy_names: Optional[List[str]] = None,
) -> StockBacktestSummary:
    """Run historical backtests for all strategies.

    Rules:
    - Minimum history: at least 1 calendar year (365 days span).
      If < 1 year: return '歷史資料不足 1 年，無法回測', do not show win rate.
    - Backtest window: up to the most recent 5 years of daily data.
    - Two runs per strategy:
      1. Three-layer conditions (fundamental & chips & technical)
      2. Pure technical conditions
    """
    if daily_k.empty:
        raise ValueError(f"No daily K data for stock {stock_id}")

    dates = pd.to_datetime(daily_k["date"])
    evaluation_date = str(daily_k["date"].iloc[-1])
    min_date = dates.min()
    max_date = dates.max()
    span_days = (max_date - min_date).days

    strats = strategy_names or params.ALL_STRATEGIES

    # Rule: at least 1 year required
    if span_days < 365:
        msg = "歷史資料不足 1 年，無法回測"
        results = [
            StrategyBacktestResult(
                strategy_name=name,
                can_backtest=False,
                message=msg,
                three_layer=None,
                tech_only=None,
                three_layer_trades=[],
                tech_only_trades=[],
            )
            for name in strats
        ]
        return StockBacktestSummary(
            stock_id=stock_id,
            evaluation_date=evaluation_date,
            can_backtest=False,
            message=msg,
            results=results,
        )

    # 5-year window cutoff
    cutoff_date = (max_date - pd.DateOffset(years=5)).strftime("%Y-%m-%d")

    # 1. Compute indicators and layers on full dataset
    df_ind = compute_all_indicators(daily_k)
    fund_df = evaluate_fundamentals_series(daily_k, monthly_revenue, quarterly_financials)
    chips_df = evaluate_chips_series(daily_k, institutional_investors, margin_short)
    strat_signals = evaluate_all_strategies(df_ind)

    # 2. Slice to the 5-year window
    window_mask = (df_ind["date"] >= cutoff_date).values
    df_window = df_ind.iloc[window_mask].reset_index(drop=True)
    fund_pass = fund_df.iloc[window_mask]["fundamental_pass"].reset_index(drop=True)
    chips_pass = chips_df.iloc[window_mask]["chips_pass"].reset_index(drop=True)

    results: List[StrategyBacktestResult] = []

    for name in strats:
        tech_sig = strat_signals[name].iloc[window_mask].reset_index(drop=True)

        # Three-layer signal mask: fundamental AND chips AND technical
        three_layer_sig = fund_pass & chips_pass & tech_sig

        # 1. Three-layer backtest
        three_trades = run_backtest(df_window, three_layer_sig)
        three_stats = compute_stats(three_trades)

        # 2. Pure technical backtest
        tech_trades = run_backtest(df_window, tech_sig)
        tech_stats = compute_stats(tech_trades)

        results.append(
            StrategyBacktestResult(
                strategy_name=name,
                can_backtest=True,
                message=None,
                three_layer=three_stats,
                tech_only=tech_stats,
                three_layer_trades=three_trades,
                tech_only_trades=tech_trades,
            )
        )

    return StockBacktestSummary(
        stock_id=stock_id,
        evaluation_date=evaluation_date,
        can_backtest=True,
        message=None,
        results=results,
    )
