"""Unit tests covering the error handling and warning requirements of market-data spec."""
from datetime import datetime
import pandas as pd
import pytest

from app.data.cache import CacheRepository
from app.data.exceptions import (
    FinMindQuotaExceededError,
    FinMindTokenMissingError,
)
from app.data.finmind_client import FinMindClient
from app.data.service import TAIPEI_TZ, DataService


class QuotaFailingClient(FinMindClient):
    """Client that always throws FinMindQuotaExceededError."""

    def __init__(self):
        super().__init__(token="mock_token")

    def get_daily_k(self, stock_id: str, start_date: str, end_date: str = None, adjusted: bool = True):
        raise FinMindQuotaExceededError()


def test_quota_exceeded_with_cache():
    """When quota exceeded but cache exists up to 3 days ago, use cache and attach warning."""
    repo = CacheRepository(db_path=":memory:")
    stock_id = "2330"

    # Prepopulate cache with data up to 3 days ago (e.g. 2024-05-17)
    df_k = pd.DataFrame([
        {"date": "2024-05-15", "open": 500.0, "high": 505.0, "low": 495.0, "close": 502.0, "volume": 10000},
        {"date": "2024-05-16", "open": 502.0, "high": 508.0, "low": 500.0, "close": 506.0, "volume": 12000},
        {"date": "2024-05-17", "open": 506.0, "high": 510.0, "low": 504.0, "close": 508.0, "volume": 15000},
    ])
    repo.upsert_daily_k(stock_id, df_k)
    repo.update_fetch_log(stock_id, "daily_k", "2024-05-17")

    client = QuotaFailingClient()
    service = DataService(client=client, repo=repo)

    # Sync on 2024-05-20
    dt_now = datetime(2024, 5, 20, 16, 0, tzinfo=TAIPEI_TZ)
    result = service.sync_stock(stock_id, current_dt=dt_now)

    assert result.quota_exceeded is True
    # Warning must be attached
    assert any("資料截至 2024-05-17，API 額度已用盡" in w for w in result.warnings)
    # Cached data remains available
    cached_k = repo.get_daily_k(stock_id)
    assert len(cached_k) == 3


def test_quota_exceeded_without_cache():
    """When quota exceeded and no cache exists, raise FinMindQuotaExceededError."""
    repo = CacheRepository(db_path=":memory:")
    stock_id = "2330"

    client = QuotaFailingClient()
    service = DataService(client=client, repo=repo)

    dt_now = datetime(2024, 5, 20, 16, 0, tzinfo=TAIPEI_TZ)
    with pytest.raises(FinMindQuotaExceededError) as exc_info:
        service.sync_stock(stock_id, current_dt=dt_now)

    assert exc_info.value.code == "QUOTA_EXCEEDED"
    assert "API 額度已用盡，請稍後再試" in str(exc_info.value)


def test_stock_listed_less_than_five_years():
    """When a stock has only 2 years of history, attach warning '歷史資料僅 2 年'."""
    repo = CacheRepository(db_path=":memory:")
    stock_id = "6888"

    # Prepopulate with 2 years of data: 2022-05-20 to 2024-05-20
    df_k = pd.DataFrame([
        {"date": "2022-05-20", "open": 50.0, "high": 52.0, "low": 49.0, "close": 51.0, "volume": 1000},
        {"date": "2024-05-20", "open": 80.0, "high": 82.0, "low": 79.0, "close": 81.0, "volume": 2000},
    ])
    repo.upsert_daily_k(stock_id, df_k)
    repo.update_fetch_log(stock_id, "daily_k", "2024-05-20")
    for ds in ["institutional_investors", "margin_short", "monthly_revenue", "quarterly_financials"]:
        repo.update_fetch_log(stock_id, ds, "2024-05-20")

    client = FinMindClient(token="mock_token")
    service = DataService(client=client, repo=repo)

    dt_now = datetime(2024, 5, 20, 16, 0, tzinfo=TAIPEI_TZ)
    result = service.sync_stock(stock_id, current_dt=dt_now)

    assert any("歷史資料僅 2 年" in w for w in result.warnings)


def test_token_missing_error():
    """When token is missing, raise FinMindTokenMissingError."""
    repo = CacheRepository(db_path=":memory:")
    stock_id = "2330"

    client = FinMindClient(token="")
    service = DataService(client=client, repo=repo)

    dt_now = datetime(2024, 5, 20, 16, 0, tzinfo=TAIPEI_TZ)
    with pytest.raises(FinMindTokenMissingError) as exc_info:
        service.sync_stock(stock_id, current_dt=dt_now)

    assert exc_info.value.code == "TOKEN_MISSING"
    assert "尚未設定 FinMind token" in str(exc_info.value)
