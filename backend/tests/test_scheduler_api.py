from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.scheduler import get_scheduler_status, init_scheduler, start_scheduler, stop_scheduler
from app.data.service import DataService
from app.data.twse_client import DailyQuote
from app.main import app


@pytest.fixture
def mock_service():
    repo = CacheRepository(":memory:")
    client = MagicMock()
    service = DataService(client=client, repo=repo)
    return service


@pytest.fixture
def client(mock_service):
    app.dependency_overrides[get_data_service] = lambda: mock_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_get_nightly_plan_empty(client):
    resp = client.get("/api/scanner/nightly-plan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["items"] == []
    assert "scheduler_status" in data


def test_get_nightly_plan_with_data(client, mock_service):
    # Save a plan directly into the repo
    mock_service.repo.save_nightly_plan(
        scan_date="2026-10-26",
        items=[
            {
                "stock_id": "2330",
                "stock_name": "台積電",
                "market": "上市",
                "strategy": "布林通道突破",
                "win_rate": 0.8,
                "trade_count": 20,
                "entry_price": 1000.0,
                "stop_loss": 950.0,
                "take_profit": 1080.0,
                "holding_days": 20,
                "risk_reward_ratio": 1.6,
                "close_price": 1000.0,
                "volume": 20000000,
                "reason": "三層濾網通過",
            }
        ],
        plan_id="plan_test_api",
        total_candidates=35,
        notes="測試用作戰清單",
    )

    resp = client.get("/api/scanner/nightly-plan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["plan_id"] == "plan_test_api"
    assert data["scan_date"] == "2026-10-26"
    assert data["total_candidates"] == 35
    assert len(data["items"]) == 1
    assert data["items"][0]["stock_id"] == "2330"
    assert data["items"][0]["win_rate"] == 0.8
    assert data["items"][0]["risk_reward_ratio"] == 1.6

    # Test with specific date query
    resp_date = client.get("/api/scanner/nightly-plan?date=2026-10-26")
    assert resp_date.status_code == 200
    assert resp_date.json()["found"] is True

    # Test with non-existent date
    resp_none = client.get("/api/scanner/nightly-plan?date=2020-01-01")
    assert resp_none.status_code == 200
    assert resp_none.json()["found"] is False


@patch("app.data.scheduler.run_two_stage_scan")
def test_trigger_nightly_plan_endpoint(mock_scan, client, mock_service):
    # Mock two-stage scan returning 1 matched stock
    mock_scan.return_value = {
        "total": 30,
        "scanned": 30,
        "matched_count": 1,
        "quota_exceeded": False,
        "warnings": [],
        "results": [
            {
                "stock_id": "2454",
                "stock_name": "聯發科",
                "market": "上市",
                "type": "twse",
                "close": 1250.0,
                "entry_price": 1250.0,
                "stop_loss": 1190.0,
                "take_profit": 1350.0,
                "max_holding_days": 20,
                "risk_reward_ratio": 1.67,
                "best_strategy_name": "均線糾結突破",
                "best_win_rate_pct": 75.0,
                "triggered_strategies": ["均線糾結突破"],
                "strategy_stats": [{"strategy_name": "均線糾結突破"}],
            }
        ],
    }

    resp = client.post("/api/scanner/nightly-plan/trigger", json={"scan_date": "2026-10-26"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["selected_count"] == 1
    assert data["plan_id"].startswith("plan_")

    # Verify saved in repo
    latest = mock_service.repo.get_latest_nightly_plan()
    assert latest is not None
    assert latest["scan_date"] == "2026-10-26"
    assert len(latest["items"]) == 1
    assert latest["items"][0]["stock_id"] == "2454"


def test_scheduler_lifecycle():
    sched = init_scheduler()
    assert sched is not None

    start_scheduler()
    status = get_scheduler_status()
    assert status["running"] is True
    assert "cron" in status

    stop_scheduler()
    status_stopped = get_scheduler_status()
    assert status_stopped["running"] is False
