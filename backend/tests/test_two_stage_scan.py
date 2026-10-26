from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from app.analysis.exits import calculate_exit_levels, round_to_tick
from app.analysis.scanner import (
    ScanFilterConfig,
    resolve_scan_pool,
    run_scan,
    run_two_stage_scan,
)
from app.data.cache import CacheRepository
from app.data.service import DataService
from app.data.twse_client import DailyQuote, TWSEClient


def _make_dummy_daily_k(stock_id: str, n: int = 100, end_price: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="B").strftime("%Y-%m-%d")
    prices = np.linspace(end_price * 0.8, end_price, n)
    return pd.DataFrame({
        "stock_id": stock_id,
        "date": dates,
        "open": prices * 0.99,
        "high": prices * 1.02,
        "low": prices * 0.98,
        "close": prices,
        "volume": 2000000,
        "money": prices * 2000000,
        "spread": 1.0,
        "turnover": 0.5,
        "effective_date": dates,
    })


@pytest.fixture
def mock_service():
    repo = CacheRepository(":memory:")
    finmind = MagicMock()
    service = DataService(client=finmind, repo=repo)

    # Seed stock_info
    repo.upsert_stock_info(pd.DataFrame([
        {"stock_id": "2330", "stock_name": "台積電", "type": "twse", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "2454", "stock_name": "聯發科", "type": "twse", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "9999", "stock_name": "弱勢股", "type": "twse", "industry_category": "其他", "is_supported": 1},
    ]))

    # Seed daily_k
    dk_2330 = _make_dummy_daily_k("2330", 100, 1000.0)
    dk_2454 = _make_dummy_daily_k("2454", 100, 1200.0)
    repo.upsert_daily_k("2330", dk_2330)
    repo.upsert_daily_k("2454", dk_2454)

    # Seed monthly revenue & quarterly financials (L2 pass)
    rev = pd.DataFrame([
        {"stock_id": "2330", "date": "2025-09-01", "revenue_year": 2025, "revenue_month": 9, "revenue": 100000000.0, "effective_date": "2025-10-10"},
        {"stock_id": "2330", "date": "2026-09-01", "revenue_year": 2026, "revenue_month": 9, "revenue": 120000000.0, "effective_date": "2026-10-10"},
    ])
    repo.upsert_monthly_revenue("2330", rev)

    fin = pd.DataFrame([
        {"stock_id": "2330", "date": "2025-09-30", "year": 2025, "quarter": 3, "eps": 8.0, "debt_ratio": 30.0, "effective_date": "2025-11-14"},
        {"stock_id": "2330", "date": "2025-12-31", "year": 2025, "quarter": 4, "eps": 8.0, "debt_ratio": 30.0, "effective_date": "2026-03-31"},
        {"stock_id": "2330", "date": "2026-03-31", "year": 2026, "quarter": 1, "eps": 9.0, "debt_ratio": 30.0, "effective_date": "2026-05-15"},
        {"stock_id": "2330", "date": "2026-06-30", "year": 2026, "quarter": 2, "eps": 10.0, "debt_ratio": 30.0, "effective_date": "2026-08-14"},
    ])
    repo.upsert_quarterly_financials("2330", fin)

    # Seed institutional investors (L3 pass)
    inst = pd.DataFrame([{
        "stock_id": "2330",
        "date": "2026-10-26",
        "foreign_buy": 1000000,
        "foreign_sell": 500000,
        "investment_trust_buy": 200000,
        "investment_trust_sell": 50000,
        "dealer_buy": 0,
        "dealer_sell": 0,
        "effective_date": "2026-10-26",
    }])
    repo.upsert_institutional_investors("2330", inst)

    return service


def test_two_stage_scan_pool_resolution(mock_service):
    mock_twse_client = MagicMock(spec=TWSEClient)
    # Simulate TWSE returning 1000+ market quotes, but filter_candidates selects only 2
    mock_quotes = [
        DailyQuote("2330", "台積電", "2026-10-26", 990.0, 1010.0, 990.0, 1000.0, 10.0, 1.0, 20_000_000, 20_000.0, "TWSE"),
        DailyQuote("2454", "聯發科", "2026-10-26", 1180.0, 1210.0, 1180.0, 1200.0, 20.0, 1.7, 5_000_000, 5_000.0, "TWSE"),
        DailyQuote("9999", "低量弱勢", "2026-10-26", 10.0, 10.0, 9.5, 9.5, -0.5, -5.0, 100_000, 100.0, "TWSE"),
    ]
    mock_twse_client.fetch_all_quotes.return_value = mock_quotes
    mock_twse_client.filter_candidates.return_value = [mock_quotes[0], mock_quotes[1]]

    config = ScanFilterConfig(
        two_stage=True,
        scan_date="2026-10-26",
        pool="all",
        min_volume_lots=1000.0,
        top_candidates=50,
    )

    stocks = resolve_scan_pool(mock_service, config, twse_client=mock_twse_client)
    assert len(stocks) == 2
    assert stocks[0]["stock_id"] == "2330"
    assert stocks[1]["stock_id"] == "2454"

    # Verify mock_twse_client was called with target date
    mock_twse_client.fetch_all_quotes.assert_called_once_with("2026-10-26")


def test_two_stage_scan_exits_and_api_calls(mock_service):
    mock_twse_client = MagicMock(spec=TWSEClient)
    candidate_quote = DailyQuote(
        "2330", "台積電", "2026-10-26", 990.0, 1010.0, 990.0, 1000.0, 10.0, 1.0, 20_000_000, 20_000.0, "TWSE"
    )
    mock_twse_client.fetch_all_quotes.return_value = [candidate_quote]
    mock_twse_client.filter_candidates.return_value = [candidate_quote]

    # Run two stage scan with require_fundamental=False, require_chips=False to inspect exits
    res = run_two_stage_scan(
        service=mock_service,
        twse_client=mock_twse_client,
        scan_date="2026-10-26",
        min_volume_lots=1000.0,
        min_price=10.0,
        top_candidates=10,
        require_fundamental=False,
        require_chips=False,
    )

    assert res["total"] == 1
    assert res["scanned"] == 1
    # Verify FinMind API calls were only triggered for the 1 candidate, not entire market
    sync_calls = mock_service.client.fetch_daily_k.call_count
    assert sync_calls <= 1

    if res["matched_count"] > 0:
        match = res["results"][0]
        # Check exit levels are present
        assert match["entry_price"] is not None
        assert match["stop_loss"] is not None
        assert match["take_profit"] is not None
        assert match["max_holding_days"] is not None
        assert match["risk_reward_ratio"] is not None

        # Verify stop loss < entry price < take profit
        assert match["stop_loss"] < match["entry_price"]
        assert match["take_profit"] > match["entry_price"]
        assert match["risk_reward_ratio"] > 0


def test_exit_levels_tick_rounding():
    # Test price tick rounding rule
    # For price 1000, tick size is 5.0
    entry = 1000.0
    atr = 25.0
    stop, take, days = calculate_exit_levels(entry, atr)
    # stop = 1000 - 2 * 25 = 950.0
    # take = 1000 + 3 * 25 = 1075.0
    assert stop == 950.0
    assert take == 1075.0
    assert days == 20
    assert round_to_tick(stop) == stop
    assert round_to_tick(take) == take
