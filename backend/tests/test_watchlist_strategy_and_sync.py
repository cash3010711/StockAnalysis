import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pandas as pd

from app.analysis.assembler import ChipsSummary, FundamentalSummary, StrategyAnalysisResult, TodayAnalysis
from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.service import DataService, SyncResult
from app.main import app


@pytest.fixture
def test_setup():
    repo = CacheRepository(db_path=":memory:")
    service = DataService(repo=repo)

    # Seed 2330 in watchlist
    repo.add_watchlist_item("2330", "台積電", "2026-10-21", 980.0)

    # Create dummy 25 daily_k rows for 2330
    dates = pd.date_range("2026-09-01", periods=25, freq="D").strftime("%Y-%m-%d")
    df_k = pd.DataFrame([
        {
            "stock_id": "2330",
            "date": d,
            "open": 950.0 + i,
            "high": 960.0 + i,
            "low": 940.0 + i,
            "close": 955.0 + i,
            "volume": 20000,
            "money": 20000000.0,
            "spread": 1.0,
            "turnover": 4000,
            "effective_date": d,
        }
        for i, d in enumerate(dates)
    ])
    repo.upsert_daily_k("2330", df_k)

    app.dependency_overrides[get_data_service] = lambda: service
    client = TestClient(app)
    yield client, service
    app.dependency_overrides.clear()
    repo.close()


def test_watchlist_strategy_evaluation_entry(test_setup):
    client, service = test_setup

    mock_analysis = TodayAnalysis(
        stock_id="2330",
        evaluation_date="2026-09-25",
        disclaimer="免責聲明",
        fundamental=FundamentalSummary(passed=True, revenue_yoy=0.2, eps_4q_sum=40.0, debt_ratio=0.3, reason=""),
        chips=ChipsSummary(passed=True, foreign_trust_net_buy_10d=5000, margin_increase_rate_10d=0.01, reason=""),
        strategies=[
            StrategyAnalysisResult(
                strategy_name="均線拉回 20MA",
                status="進場",
                action="BUY",
                technical_signal=True,
                entry_price=980.0,
                stop_loss=930.0,
                take_profit=1060.0,
                max_holding_days=20,
            )
        ],
    )

    with patch("app.api.watchlist.assemble_today_analysis", return_value=mock_analysis):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        item = items[0]
        assert item["stock_id"] == "2330"
        assert item["suggested_strategy"] == "均線拉回 20MA"
        assert item["entry_price"] == 980.0
        assert item["stop_loss"] == 930.0
        assert item["take_profit"] == 1060.0
        assert item["trigger_condition"] is None


def test_watchlist_strategy_evaluation_wait(test_setup):
    client, service = test_setup

    mock_analysis = TodayAnalysis(
        stock_id="2330",
        evaluation_date="2026-09-25",
        disclaimer="免責聲明",
        fundamental=FundamentalSummary(passed=True, revenue_yoy=0.2, eps_4q_sum=40.0, debt_ratio=0.3, reason=""),
        chips=ChipsSummary(passed=True, foreign_trust_net_buy_10d=5000, margin_increase_rate_10d=0.01, reason=""),
        strategies=[
            StrategyAnalysisResult(
                strategy_name="帶量突破 20 日新高",
                status="觀望",
                action="WAIT",
                technical_signal=False,
                trigger_condition="收盤突破 1000 元",
            )
        ],
    )

    with patch("app.api.watchlist.assemble_today_analysis", return_value=mock_analysis):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        item = items[0]
        assert item["stock_id"] == "2330"
        assert item["suggested_strategy"] == "觀望"
        assert item["entry_price"] is None
        assert item["stop_loss"] is None
        assert item["take_profit"] is None
        assert item["trigger_condition"] == "收盤突破 1000 元"


def test_watchlist_sync_endpoint(test_setup):
    client, service = test_setup

    mock_sync_result = SyncResult(stock_id="2330", target_date="2026-10-27")
    service.sync_stock = MagicMock(return_value=mock_sync_result)

    resp = client.post("/api/watchlist/sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["synced_count"] == 1
    assert data["total_count"] == 1
    assert "items" in data
    assert service.sync_stock.called
