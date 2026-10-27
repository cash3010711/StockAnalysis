"""Assembly of today's three-layer stock analysis."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import pandas as pd

from app.analysis import params
from app.analysis.exits import calculate_exit_levels, round_to_tick
from app.analysis.indicators import compute_all_indicators
from app.analysis.layers import (
    evaluate_chips_series,
    evaluate_fundamentals_series,
)
from app.analysis.strategies import (
    evaluate_all_strategies,
    get_strategy_trigger_description,
)
from app.backtest.stats import BacktestStats, EquityPoint


@dataclass
class FundamentalSummary:
    """Fundamental layer summary for evaluation date."""

    passed: bool
    revenue_yoy: Optional[float]
    eps_4q_sum: Optional[float]
    debt_ratio: Optional[float]
    reason: str


@dataclass
class ChipsSummary:
    """Chips layer summary for evaluation date."""

    passed: bool
    foreign_trust_net_buy_10d: Optional[float]
    margin_increase_rate_10d: Optional[float]
    reason: str


@dataclass
class StrategyAnalysisResult:
    """Analysis result for a single trading strategy on evaluation date."""

    strategy_name: str
    status: str  # "進場" or "觀望"
    action: str  # "BUY" or "WAIT"
    technical_signal: bool
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_holding_days: Optional[int] = None
    trigger_condition: Optional[str] = None


@dataclass
class TodayAnalysis:
    """Complete three-layer analysis result for evaluation date."""

    stock_id: str
    evaluation_date: str
    disclaimer: str
    fundamental: FundamentalSummary
    chips: ChipsSummary
    strategies: List[StrategyAnalysisResult]

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary."""
        return asdict(self)


def assemble_today_analysis(
    stock_id: str,
    daily_k: pd.DataFrame,
    monthly_revenue: pd.DataFrame,
    quarterly_financials: pd.DataFrame,
    institutional_investors: pd.DataFrame,
    margin_short: pd.DataFrame,
) -> TodayAnalysis:
    """Assemble today's analysis by evaluating fundamental, chips, and technical layers.

    Guarantees:
    - If fundamental fails: all strategies are '觀望', top displays reason, no trigger price given.
    - If fundamental & chips pass, but technical fails: displays '觀望' with specific trigger price.
    - If all 3 layers pass: displays '進場' with entry_price, stop_loss, take_profit, max_holding_days.
    """
    if daily_k.empty:
        raise ValueError(f"No daily K-bar data available for stock {stock_id}")

    # 1. Compute indicators
    df_ind = compute_all_indicators(daily_k)

    # 2. Daily evaluation series
    fund_df = evaluate_fundamentals_series(daily_k, monthly_revenue, quarterly_financials)
    chips_df = evaluate_chips_series(daily_k, institutional_investors, margin_short)
    strat_signals = evaluate_all_strategies(df_ind)

    # 3. Last closed trading day
    eval_row = df_ind.iloc[-1]
    evaluation_date = str(eval_row["date"])
    close = float(eval_row["close"])
    atr14 = float(eval_row["atr14"]) if pd.notna(eval_row.get("atr14")) else 0.0

    last_fund = fund_df.iloc[-1]
    last_chips = chips_df.iloc[-1]

    fund_passed = bool(last_fund["fundamental_pass"])
    chips_passed = bool(last_chips["chips_pass"])

    fundamental_summary = FundamentalSummary(
        passed=fund_passed,
        revenue_yoy=float(last_fund["revenue_yoy"]) if pd.notna(last_fund["revenue_yoy"]) else None,
        eps_4q_sum=float(last_fund["eps_4q_sum"]) if pd.notna(last_fund["eps_4q_sum"]) else None,
        debt_ratio=float(last_fund["debt_ratio"]) if pd.notna(last_fund["debt_ratio"]) else None,
        reason=str(last_fund["fundamental_reason"]),
    )

    chips_summary = ChipsSummary(
        passed=chips_passed,
        foreign_trust_net_buy_10d=(
            float(last_chips["foreign_trust_net_buy_10d"])
            if pd.notna(last_chips["foreign_trust_net_buy_10d"])
            else None
        ),
        margin_increase_rate_10d=(
            float(last_chips["margin_increase_rate_10d"])
            if pd.notna(last_chips["margin_increase_rate_10d"])
            else None
        ),
        reason=str(last_chips["chips_reason"]),
    )

    strategy_results: List[StrategyAnalysisResult] = []

    for strat_name in params.ALL_STRATEGIES:
        sig_series = strat_signals[strat_name]
        tech_signal = bool(sig_series.iloc[-1])

        # All 3 layers must pass for entry
        if fund_passed and chips_passed and tech_signal:
            stop_loss, take_profit, max_days = calculate_exit_levels(close, atr14)
            strategy_results.append(
                StrategyAnalysisResult(
                    strategy_name=strat_name,
                    status="進場",
                    action="BUY",
                    technical_signal=True,
                    entry_price=round_to_tick(close),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    max_holding_days=max_days,
                    trigger_condition=None,
                )
            )
        else:
            # Watch (觀望)
            # Trigger price is only provided when fundamental AND chips passed, but technical failed
            trigger_cond: Optional[str] = None
            if fund_passed and chips_passed and not tech_signal:
                raw_desc = get_strategy_trigger_description(strat_name, df_ind, idx=-1)
                trigger_cond = f"觀望：{raw_desc}" if not raw_desc.startswith("觀望：") else raw_desc
            else:
                trigger_cond = None

            strategy_results.append(
                StrategyAnalysisResult(
                    strategy_name=strat_name,
                    status="觀望",
                    action="WAIT",
                    technical_signal=tech_signal,
                    entry_price=None,
                    stop_loss=None,
                    take_profit=None,
                    max_holding_days=None,
                    trigger_condition=trigger_cond,
                )
            )

    return TodayAnalysis(
        stock_id=stock_id,
        evaluation_date=evaluation_date,
        disclaimer=params.DISCLAIMER_TEXT,
        fundamental=fundamental_summary,
        chips=chips_summary,
        strategies=strategy_results,
    )
