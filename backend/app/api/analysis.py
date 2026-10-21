"""Analysis API endpoint."""
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
import pandas as pd
from pydantic import BaseModel

from app.analysis.assembler import assemble_today_analysis
from app.api.stocks import get_data_service
from app.backtest.runner import run_all_backtests
from app.data.exceptions import (
    InsufficientDataError,
    StockNotSupportedError,
)
from app.data.service import DataService


class FundamentalSummaryModel(BaseModel):
    passed: bool
    revenue_yoy: Optional[float] = None
    eps_4q_sum: Optional[float] = None
    debt_ratio: Optional[float] = None
    reason: str


class ChipsSummaryModel(BaseModel):
    passed: bool
    foreign_trust_net_buy_10d: Optional[float] = None
    margin_increase_rate_10d: Optional[float] = None
    reason: str


class TradeModel(BaseModel):
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    stop_loss: float
    take_profit: float
    holding_days: int
    gross_return: float
    net_return: float
    exit_reason: str
    is_win: bool


class BacktestStatsModel(BaseModel):
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: Optional[float] = None
    win_rate_pct: Optional[float] = None
    avg_return: Optional[float] = None
    avg_return_pct: Optional[float] = None
    expected_value: Optional[float] = None
    expected_value_pct: Optional[float] = None
    avg_holding_days: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    insufficient_sample: bool
    has_trades: bool
    status_text: Optional[str] = None


class StrategyItemModel(BaseModel):
    strategy_name: str
    status: str
    action: str
    technical_signal: bool
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_holding_days: Optional[int] = None
    trigger_condition: Optional[str] = None
    can_backtest: bool
    backtest_message: Optional[str] = None
    three_layer_stats: Optional[BacktestStatsModel] = None
    tech_only_stats: Optional[BacktestStatsModel] = None
    three_layer_trades: List[TradeModel] = []
    tech_only_trades: List[TradeModel] = []


class OHLCVItemModel(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class AnalysisResponse(BaseModel):
    stock_id: str
    stock_name: str
    evaluation_date: str
    disclaimer: str
    warnings: List[str]
    fundamental: FundamentalSummaryModel
    chips: ChipsSummaryModel
    strategies: List[StrategyItemModel]
    ohlcv: List[OHLCVItemModel]


router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/analysis/{stock_id}", response_model=AnalysisResponse)
def analyze_stock(
    stock_id: str,
    service: DataService = Depends(get_data_service),
):
    """Run full three-layer stock analysis and historical backtest."""
    sid = (stock_id or "").strip()
    if not sid or len(sid) != 4 or not sid.isdigit():
        raise StockNotSupportedError()

    if service.repo.is_unsupported_stock(sid):
        raise StockNotSupportedError()

    # Sync fresh data
    sync_result = service.sync_stock(sid)

    # Determine evaluation date
    eval_date = sync_result.latest_k_date
    if not eval_date:
        raise InsufficientDataError(
            message="歷史資料不足，無法進行分析",
            hint="查無該股票的歷史日 K 資料",
        )

    # Point-in-time data as of eval_date
    data = service.as_of(sid, eval_date)
    daily_k = data.get("daily_k", pd.DataFrame())

    if daily_k.empty or len(daily_k) < 35:
        raise InsufficientDataError(
            message="歷史資料不足，無法進行分析",
            hint="歷史交易日過少（需至少 35 個交易日），尚無法計算技術指標",
        )

    # 1. Assemble today's analysis
    today_analysis = assemble_today_analysis(
        stock_id=sid,
        daily_k=daily_k,
        monthly_revenue=data.get("monthly_revenue", pd.DataFrame()),
        quarterly_financials=data.get("quarterly_financials", pd.DataFrame()),
        institutional_investors=data.get("institutional_investors", pd.DataFrame()),
        margin_short=data.get("margin_short", pd.DataFrame()),
    )

    # 2. Run historical backtests
    backtest_summary = run_all_backtests(
        stock_id=sid,
        daily_k=daily_k,
        monthly_revenue=data.get("monthly_revenue", pd.DataFrame()),
        quarterly_financials=data.get("quarterly_financials", pd.DataFrame()),
        institutional_investors=data.get("institutional_investors", pd.DataFrame()),
        margin_short=data.get("margin_short", pd.DataFrame()),
    )

    bt_by_name = {r.strategy_name: r for r in backtest_summary.results}

    combined_strategies: List[Dict[str, Any]] = []
    for strat in today_analysis.strategies:
        bt = bt_by_name.get(strat.strategy_name)
        combined_strategies.append({
            "strategy_name": strat.strategy_name,
            "status": strat.status,
            "action": strat.action,
            "technical_signal": strat.technical_signal,
            "entry_price": strat.entry_price,
            "stop_loss": strat.stop_loss,
            "take_profit": strat.take_profit,
            "max_holding_days": strat.max_holding_days,
            "trigger_condition": strat.trigger_condition,
            "can_backtest": bt.can_backtest if bt else False,
            "backtest_message": bt.message if bt else None,
            "three_layer_stats": bt.three_layer.to_dict() if bt and bt.three_layer else None,
            "tech_only_stats": bt.tech_only.to_dict() if bt and bt.tech_only else None,
            "three_layer_trades": [t.to_dict() for t in bt.three_layer_trades] if bt else [],
            "tech_only_trades": [t.to_dict() for t in bt.tech_only_trades] if bt else [],
        })

    # 3. OHLCV data for charting
    ohlcv = [
        {
            "date": str(row["date"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
        }
        for _, row in daily_k.iterrows()
    ]

    stock_name = service.get_stock_name(sid)

    return {
        "stock_id": sid,
        "stock_name": stock_name,
        "evaluation_date": eval_date,
        "disclaimer": today_analysis.disclaimer,
        "warnings": sync_result.warnings,
        "fundamental": asdict(today_analysis.fundamental),
        "chips": asdict(today_analysis.chips),
        "strategies": combined_strategies,
        "ohlcv": ohlcv,
    }
