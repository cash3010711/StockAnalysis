"""Unit tests for incremental sync flow and time cutoffs."""
from datetime import datetime
from unittest.mock import MagicMock
import pandas as pd
import pytest

from app.data.cache import CacheRepository
from app.data.finmind_client import FinMindClient
from app.data.service import TAIPEI_TZ, DataService


class CountingMockClient(FinMindClient):
    """Mock FinMindClient that counts API calls and returns dummy data."""

    def __init__(self):
        super().__init__(token="mock_token")
        self.call_history = []

    def get_daily_k(self, stock_id: str, start_date: str, end_date: str = None, adjusted: bool = True):
        self.call_history.append(("daily_k", stock_id, start_date, end_date))
        return pd.DataFrame([
            {"date": start_date, "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 5000}
        ])

    def get_institutional_investors(self, stock_id: str, start_date: str, end_date: str = None):
        self.call_history.append(("institutional_investors", stock_id, start_date, end_date))
        return pd.DataFrame([
            {"date": start_date, "name": "Foreign_Investor", "buy": 100, "sell": 50}
        ])

    def get_margin_short(self, stock_id: str, start_date: str, end_date: str = None):
        self.call_history.append(("margin_short", stock_id, start_date, end_date))
        return pd.DataFrame([
            {"date": start_date, "MarginPurchaseTodayBalance": 1000, "ShortSaleTodayBalance": 100}
        ])

    def get_monthly_revenue(self, stock_id: str, start_date: str, end_date: str = None):
        self.call_history.append(("monthly_revenue", stock_id, start_date, end_date))
        return pd.DataFrame([
            {"date": start_date, "revenue_year": 2024, "revenue_month": 4, "revenue": 500000, "effective_date": "2024-05-10"}
        ])

    def get_quarterly_financials(self, stock_id: str, start_date: str, end_date: str = None):
        self.call_history.append(("quarterly_financials", stock_id, start_date, end_date))
        return pd.DataFrame([
            {"date": start_date, "year": 2024, "quarter": 1, "eps": 2.5, "debt_ratio": 30.0, "effective_date": "2024-05-15"}
        ])


def test_taipei_1430_cutoff_rule():
    """Before 14:30 Taipei time only fetches up to yesterday; at or after 14:30 fetches up to today."""
    # 1. 2024-05-20 10:00 AM Taipei time (before 14:30)
    dt_morning = datetime(2024, 5, 20, 10, 0, tzinfo=TAIPEI_TZ)
    target_morning = DataService.get_target_trade_date(dt_morning)
    assert target_morning.isoformat() == "2024-05-19"

    # 2. 2024-05-20 14:30 PM Taipei time (exactly at 14:30)
    dt_afternoon = datetime(2024, 5, 20, 14, 30, tzinfo=TAIPEI_TZ)
    target_afternoon = DataService.get_target_trade_date(dt_afternoon)
    assert target_afternoon.isoformat() == "2024-05-20"

    # 3. 2024-05-20 16:00 PM Taipei time (after 14:30)
    dt_evening = datetime(2024, 5, 20, 16, 0, tzinfo=TAIPEI_TZ)
    target_evening = DataService.get_target_trade_date(dt_evening)
    assert target_evening.isoformat() == "2024-05-20"


def test_incremental_sync_does_not_refetch_history():
    """Verify that second sync makes 0 requests when cache is already latest."""
    repo = CacheRepository(db_path=":memory:")
    client = CountingMockClient()
    service = DataService(client=client, repo=repo)

    simulated_dt = datetime(2024, 5, 20, 15, 0, tzinfo=TAIPEI_TZ)
    stock_id = "2330"

    # 1. First sync: empty cache -> 5 requests made (one per dataset)
    res1 = service.sync_stock(stock_id, current_dt=simulated_dt)
    assert res1.requests_made == 5
    assert len(client.call_history) == 5

    # Check that initial request started 5 years ago
    daily_calls = [c for c in client.call_history if c[0] == "daily_k"]
    assert len(daily_calls) == 1
    # 5 years before 2024-05-20 is 2019-05-21
    assert daily_calls[0][2] == "2019-05-21"
    assert daily_calls[0][3] == "2024-05-20"

    # 2. Second sync immediately afterwards: already up-to-date!
    res2 = service.sync_stock(stock_id, current_dt=simulated_dt)
    assert res2.requests_made == 0
    # Client call count remains 5 (no new calls!)
    assert len(client.call_history) == 5


def test_incremental_sync_only_fetches_new_dates():
    """When cache is at 2024-05-19 and next day 2024-05-20 closes, only fetch 2024-05-20."""
    repo = CacheRepository(db_path=":memory:")
    client = CountingMockClient()
    service = DataService(client=client, repo=repo)

    stock_id = "2330"
    dt_day1 = datetime(2024, 5, 19, 16, 0, tzinfo=TAIPEI_TZ)
    service.sync_stock(stock_id, current_dt=dt_day1)
    assert len(client.call_history) == 5

    # Advance to next day after close
    dt_day2 = datetime(2024, 5, 20, 16, 0, tzinfo=TAIPEI_TZ)
    res_day2 = service.sync_stock(stock_id, current_dt=dt_day2)
    assert res_day2.requests_made == 5

    # Check new calls only requested start_date = 2024-05-20
    new_daily_calls = [c for c in client.call_history[5:] if c[0] == "daily_k"]
    assert len(new_daily_calls) == 1
    assert new_daily_calls[0][2] == "2024-05-20"
    assert new_daily_calls[0][3] == "2024-05-20"
