"""Unit tests for /api/watchlist endpoints."""
import pytest
from fastapi.testclient import TestClient
import pandas as pd

from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.service import DataService
from app.main import app


@pytest.fixture
def test_client():
    """Create test client with isolated in-memory DB repository."""
    repo = CacheRepository(db_path=":memory:")
    service = DataService(repo=repo)

    # Seed daily_k for 2330
    df_k = pd.DataFrame([
        {
            "stock_id": "2330",
            "date": "2026-10-24",
            "open": 1000.0,
            "high": 1020.0,
            "low": 995.0,
            "close": 1010.0,
            "volume": 25000,
            "money": 25250000.0,
            "spread": 10.0,
            "turnover": 5000,
            "effective_date": "2026-10-24",
        },
        {
            "stock_id": "2330",
            "date": "2026-10-27",
            "open": 1020.0,
            "high": 1060.0,
            "low": 1015.0,
            "close": 1050.0,
            "volume": 30000,
            "money": 31500000.0,
            "spread": 40.0,
            "turnover": 6000,
            "effective_date": "2026-10-27",
        },
    ])
    repo.upsert_daily_k("2330", df_k)

    # Seed stock_info for 2330
    df_info = pd.DataFrame([{
        "stock_id": "2330",
        "stock_name": "台積電",
        "type": "twse",
        "industry_category": "半導體業",
        "is_supported": 1,
    }])
    repo.upsert_stock_info(df_info)

    app.dependency_overrides[get_data_service] = lambda: service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    repo.close()


def test_watchlist_api_flow(test_client):
    """Test full CRUD flow via API."""
    # 1. GET initially empty
    resp = test_client.get("/api/watchlist")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. POST create with explicit values
    create_payload = {
        "stock_id": "2330",
        "stock_name": "台積電",
        "added_date": "2026-10-24",
        "added_price": 1000.0,
        "notes": "長期持有",
    }
    resp = test_client.post("/api/watchlist", json=create_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["stock_id"] == "2330"
    assert data["stock_name"] == "台積電"
    assert data["added_price"] == 1000.0
    assert data["current_price"] == 1050.0
    # Change pct: (1050 - 1000) / 1000 = 5.0%
    assert data["change_pct"] == 5.0
    assert data["return_pct"] == 5.0
    assert data["notes"] == "長期持有"

    # 3. Prevent duplicate insert
    resp_dup = test_client.post("/api/watchlist", json=create_payload)
    assert resp_dup.status_code == 400
    assert "已在自選股清單中" in resp_dup.json()["detail"]

    # 4. GET lists items with current price and return
    resp_list = test_client.get("/api/watchlist")
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 1
    assert items[0]["stock_id"] == "2330"
    assert items[0]["current_price"] == 1050.0
    assert items[0]["change_pct"] == 5.0

    # 5. DELETE existing stock
    del_resp = test_client.delete("/api/watchlist/2330")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 6. DELETE non-existent stock returns 404
    del_404 = test_client.delete("/api/watchlist/2330")
    assert del_404.status_code == 404

    # 7. List is empty again
    resp_empty = test_client.get("/api/watchlist")
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []


def test_watchlist_create_defaults(test_client):
    """Test POST create with defaults populated from stock_info and daily_k."""
    resp = test_client.post("/api/watchlist", json={"stock_id": "2330"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["stock_id"] == "2330"
    assert data["stock_name"] == "台積電"
    assert data["added_date"] == "2026-10-27"
    assert data["added_price"] == 1050.0
    assert data["current_price"] == 1050.0
    assert data["change_pct"] == 0.0
