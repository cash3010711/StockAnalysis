"""Watchlist API router for managing personal tracked stocks."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
import pandas as pd
from pydantic import BaseModel, Field

from app.api.stocks import get_data_service
from app.data.service import DataService

router = APIRouter(prefix="/api", tags=["watchlist"])


class WatchlistItemModel(BaseModel):
    stock_id: str
    stock_name: str
    added_date: str
    added_price: float
    current_price: Optional[float] = None
    current_date: Optional[str] = None
    change_pct: Optional[float] = None
    return_pct: Optional[float] = None
    notes: Optional[str] = ""
    created_at: Optional[str] = None


class WatchlistCreateRequest(BaseModel):
    stock_id: str = Field(..., description="股票代號，例如 2330")
    stock_name: Optional[str] = Field(None, description="股票名稱，若為空自動帶入")
    added_date: Optional[str] = Field(None, description="加入日期 YYYY-MM-DD，若為空自動帶入最新收盤日或今日")
    added_price: Optional[float] = Field(None, description="基準買入/加入價格，若為空自動帶入最新收盤價")
    notes: Optional[str] = Field("", description="備註")


class WatchlistDeleteResponse(BaseModel):
    success: bool
    stock_id: str
    message: str


def _enrich_watchlist_item(item: Dict[str, Any], service: DataService) -> WatchlistItemModel:
    stock_id = item["stock_id"]
    added_price = float(item.get("added_price") or 0.0)

    daily_k = service.repo.get_daily_k(stock_id)
    current_price: Optional[float] = None
    current_date: Optional[str] = None
    change_pct: Optional[float] = None

    if not daily_k.empty:
        last_row = daily_k.iloc[-1]
        if pd.notna(last_row.get("close")):
            current_price = round(float(last_row["close"]), 2)
            current_date = str(last_row["date"])
            if added_price > 0:
                change_pct = round((current_price - added_price) / added_price * 100, 2)
            else:
                change_pct = 0.0

    return WatchlistItemModel(
        stock_id=stock_id,
        stock_name=item.get("stock_name") or service.get_stock_name(stock_id),
        added_date=item.get("added_date") or "",
        added_price=added_price,
        current_price=current_price,
        current_date=current_date,
        change_pct=change_pct,
        return_pct=change_pct,
        notes=item.get("notes") or "",
        created_at=str(item.get("created_at") or ""),
    )


@router.get("/watchlist", response_model=List[WatchlistItemModel])
def get_watchlist(
    service: DataService = Depends(get_data_service),
):
    """Retrieve all tracked watchlist stocks with their latest prices and return rates."""
    raw_items = service.repo.get_watchlist()
    return [_enrich_watchlist_item(item, service) for item in raw_items]


@router.post("/watchlist", response_model=WatchlistItemModel, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    request: WatchlistCreateRequest,
    service: DataService = Depends(get_data_service),
):
    """Add a stock to personal watchlist. Returns 400 if already exists."""
    stock_id = request.stock_id.strip()
    if not stock_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stock_id cannot be empty",
        )

    # Check duplicate
    if service.repo.is_in_watchlist(stock_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"股票 {stock_id} 已在自選股清單中",
        )

    # Resolve stock name
    stock_name = (request.stock_name or "").strip()
    if not stock_name:
        stock_name = service.get_stock_name(stock_id)

    # Resolve added_price and added_date from daily_k if missing
    daily_k = service.repo.get_daily_k(stock_id)
    added_price = request.added_price
    added_date = (request.added_date or "").strip()

    if not daily_k.empty:
        last_row = daily_k.iloc[-1]
        if added_price is None and pd.notna(last_row.get("close")):
            added_price = float(last_row["close"])
        if not added_date:
            added_date = str(last_row["date"])

    if added_price is None:
        added_price = 0.0
    if not added_date:
        added_date = datetime.now().strftime("%Y-%m-%d")

    item = service.repo.add_watchlist_item(
        stock_id=stock_id,
        stock_name=stock_name,
        added_date=added_date,
        added_price=added_price,
        notes=request.notes or "",
    )

    return _enrich_watchlist_item(item, service)


@router.delete("/watchlist/{stock_id}", response_model=WatchlistDeleteResponse)
def remove_from_watchlist(
    stock_id: str,
    service: DataService = Depends(get_data_service),
):
    """Remove a stock from personal watchlist. Returns 404 if not found."""
    sid = stock_id.strip()
    deleted = service.repo.delete_watchlist_item(sid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"股票 {sid} 不在自選股清單中",
        )
    return WatchlistDeleteResponse(
        success=True,
        stock_id=sid,
        message=f"已成功自自選股清單移除股票 {sid}",
    )
