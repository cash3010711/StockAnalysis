"""Stock lookup API endpoint."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.data.service import DataService


class StockLookupItem(BaseModel):
    stock_id: str
    stock_name: str
    name: str
    market: str
    type: str
    industry_category: Optional[str] = ""


router = APIRouter(prefix="/api", tags=["stocks"])

_default_service: Optional[DataService] = None


def get_data_service() -> DataService:
    """Dependency provider for DataService."""
    global _default_service
    if _default_service is None:
        _default_service = DataService()
    return _default_service


@router.get("/stocks", response_model=List[StockLookupItem])
def search_stocks(
    q: str = Query(default="", description="股票代號或名稱"),
    service: DataService = Depends(get_data_service),
):
    """Search TWSE and TPEx common stocks by stock_id or stock_name."""
    return service.lookup_stocks(q)
