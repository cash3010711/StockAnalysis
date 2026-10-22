"""Market scanner API endpoints: options, batch run, and NDJSON streaming."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.analysis import params
from app.analysis.scanner import (
    TAIWAN_50_STOCKS,
    ScanFilterConfig,
    iter_scan_events,
    run_scan,
)
from app.api.stocks import get_data_service
from app.data.service import DataService


router = APIRouter(prefix="/api/scanner", tags=["scanner"])

SCAN_POOLS = [
    {"id": "cached", "name": "本機已快取股票"},
    {"id": "tw50", "name": "熱門權值／台灣 50 代表股"},
    {"id": "all", "name": "全市場上市櫃普通股"},
    {"id": "twse", "name": "僅上市普通股"},
    {"id": "tpex", "name": "僅上櫃普通股"},
]


class ScanOptionPool(BaseModel):
    id: str
    name: str


class ScannerOptionsResponse(BaseModel):
    pools: List[ScanOptionPool]
    industries: List[str]
    strategies: List[str]
    cached_count: int
    defaults: Dict[str, Any]


class ScanRequestModel(BaseModel):
    pool: str = Field(default="cached", description="掃描股票池: cached, tw50, all, twse, tpex, industry")
    industry_category: Optional[str] = Field(default=None, description="特定產業分類")
    sync_latest: bool = Field(default=False, description="是否向 FinMind 自動同步最新資料")
    require_fundamental: bool = Field(default=True, description="是否要求基本面合格")
    require_chips: bool = Field(default=True, description="是否要求籌碼面合格")
    strategies: List[str] = Field(default_factory=list, description="欲篩選之技術策略清單（為空代表全選）")
    limit: Optional[int] = Field(default=None, description="限制掃描檔數上限")


class StrategyStatItemModel(BaseModel):
    strategy_name: str
    can_backtest: bool
    three_layer_win_rate_pct: Optional[float] = None
    three_layer_avg_return_pct: Optional[float] = None
    tech_only_win_rate_pct: Optional[float] = None
    tech_only_avg_return_pct: Optional[float] = None


class ScanMatchedStockModel(BaseModel):
    stock_id: str
    stock_name: str
    market: str
    type: str
    industry_category: Optional[str] = ""
    close: float
    evaluation_date: str
    triggered_strategies: List[str]
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_holding_days: Optional[int] = None
    fundamental_passed: bool
    revenue_yoy: Optional[float] = None
    eps_4q_sum: Optional[float] = None
    debt_ratio: Optional[float] = None
    fundamental_reason: str
    chips_passed: bool
    foreign_trust_net_buy_10d: Optional[float] = None
    margin_increase_rate_10d: Optional[float] = None
    chips_reason: str
    best_strategy_name: Optional[str] = None
    best_win_rate_pct: Optional[float] = None
    best_avg_return_pct: Optional[float] = None
    strategy_stats: List[StrategyStatItemModel] = []


class ScanRunResponse(BaseModel):
    total: int
    scanned: int
    matched_count: int
    quota_exceeded: bool
    warnings: List[str]
    results: List[ScanMatchedStockModel]


def _build_config(req: ScanRequestModel) -> ScanFilterConfig:
    return ScanFilterConfig(
        pool=req.pool,
        industry_category=req.industry_category,
        sync_latest=req.sync_latest,
        require_fundamental=req.require_fundamental,
        require_chips=req.require_chips,
        strategies=req.strategies if req.strategies else list(params.ALL_STRATEGIES),
        limit=req.limit,
    )


@router.get("/options", response_model=ScannerOptionsResponse)
def get_scanner_options(
    service: DataService = Depends(get_data_service),
):
    """Return available pools, industries, strategies, and cached stocks count."""
    cached_ids = service.repo.get_cached_stock_ids()
    cached_count = len(cached_ids)

    industries = service.repo.get_industry_categories()
    if not industries:
        industries = sorted(
            {s["industry_category"] for s in TAIWAN_50_STOCKS if s.get("industry_category")}
        )

    return {
        "pools": SCAN_POOLS,
        "industries": industries,
        "strategies": list(params.ALL_STRATEGIES),
        "cached_count": cached_count,
        "defaults": {
            "pool": "cached" if cached_count > 0 else "tw50",
            "industry_category": None,
            "sync_latest": False,
            "require_fundamental": True,
            "require_chips": True,
            "strategies": list(params.ALL_STRATEGIES),
        },
    }


@router.post("/run", response_model=ScanRunResponse)
def run_market_scan(
    request: ScanRequestModel,
    service: DataService = Depends(get_data_service),
):
    """Run market scan synchronously and return all matched stocks."""
    config = _build_config(request)
    return run_scan(service, config)


@router.post("/stream")
def stream_market_scan(
    request: ScanRequestModel,
    service: DataService = Depends(get_data_service),
):
    """Stream market scan events using NDJSON (application/x-ndjson)."""
    config = _build_config(request)

    def event_stream():
        for event in iter_scan_events(service, config):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
