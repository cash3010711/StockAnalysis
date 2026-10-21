"""Unit and API tests for stock lookup, security filtering, and 7-day cache expiration."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pandas as pd
import pytest

from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.exceptions import StockNotSupportedError
from app.data.finmind_client import FinMindClient
from app.data.service import DataService
from app.data.stock_filter import format_market, is_supported_common_stock
from app.main import app

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "finmind" / "stock_info.json"


def load_fixture_df() -> pd.DataFrame:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)["data"]
    return pd.DataFrame(data)


class MockStockInfoClient(FinMindClient):
    """Mock client returning stock_info fixture data and tracking call counts."""

    def __init__(self, df: pd.DataFrame = None):
        super().__init__(token="mock_token")
        self.df = df if df is not None else load_fixture_df()
        self.call_count = 0

    def get_stock_info(self) -> pd.DataFrame:
        self.call_count += 1
        return self.df


# --- 1. Security Type Filtering Tests ---

def test_is_supported_common_stock_rules():
    """Verify filtering rules exclude ETF, warrants, emerging, and preferred stocks."""
    # Common stocks: supported
    assert is_supported_common_stock("2330", "台積電", "twse", "半導體業") is True
    assert is_supported_common_stock("2454", "聯發科", "twse", "半導體業") is True
    assert is_supported_common_stock("2317", "鴻海", "twse", "其他電子業") is True
    assert is_supported_common_stock("6238", "勝麗", "tpex", "其他電子類") is True
    assert is_supported_common_stock("3687", "歐買尬", "tpex", "文化創意業") is True
    assert is_supported_common_stock("5871", "中租-KY", "twse", "其他") is True

    # ETF: excluded (00xxx, or ETF in category)
    assert is_supported_common_stock("0050", "元大台灣50", "twse", "ETF") is False
    assert is_supported_common_stock("0056", "元大高股息", "twse", "ETF") is False
    assert is_supported_common_stock("00835B", "第一金科技債10+", "tpex", "上櫃指數股票型基金(ETF)") is False

    # Emerging stocks (興櫃): excluded
    assert is_supported_common_stock("1234", "某興櫃股", "emerging", "生技醫療業") is False

    # Warrants (權證): excluded (length != 4 or non-numeric)
    assert is_supported_common_stock("03001P", "某權證", "twse", "認購權證") is False
    assert is_supported_common_stock("70001", "某權證", "tpex", "") is False

    # Preferred stocks (特別股): excluded
    assert is_supported_common_stock("2881A", "富邦特", "twse", "金融保險") is False
    assert is_supported_common_stock("8916A", "光隆甲特", "tpex", "其他") is False
    assert is_supported_common_stock("2887C", "新丙特", "twse", "金融保險") is False
    assert is_supported_common_stock("2891B", "中信金乙特", "twse", "金融保險") is False

    # Indices / Other: excluded
    assert is_supported_common_stock("TAIEX", "加權指數", "twse", "大盤") is False


# --- 2. Cache 7-Day Auto Refresh & 0050 Exclusion Tests (Task 3.1) ---

def test_cache_7_day_refresh_and_exclusion():
    """Verify 0050 is excluded and cache refreshes when stale (> 7 days)."""
    repo = CacheRepository(db_path=":memory:")
    client = MockStockInfoClient()
    service = DataService(client=client, repo=repo)

    # 1. Initially empty cache -> lookup triggers fetch
    res_2330 = service.lookup_stocks("2330")
    assert client.call_count == 1
    assert len(res_2330) > 0
    assert res_2330[0]["stock_id"] == "2330"
    assert res_2330[0]["stock_name"] == "台積電"
    assert res_2330[0]["market"] == "上市"

    # 2. Query again within 7 days -> does NOT trigger another fetch
    service.lookup_stocks("2330")
    assert client.call_count == 1

    # 3. Simulate cache age = 3 days ago -> still valid (<= 7 days)
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    repo.upsert_stock_info(client.df.copy(), updated_at=three_days_ago)
    service.lookup_stocks("2330")
    assert client.call_count == 1

    # 4. Simulate cache age = 8 days ago (> 7 days) -> triggers auto refresh
    eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    with repo._get_connection() as conn:
        conn.cursor().execute("UPDATE stock_info SET updated_at = ?", (eight_days_ago,))
        conn.commit()

    service.lookup_stocks("2330")
    assert client.call_count == 2

    # 5. Confirm 0050 is excluded from supported search and recognized as unsupported
    assert not any(s["stock_id"] == "0050" for s in repo.search_stocks("0050"))
    assert repo.is_unsupported_stock("0050") is True

    # 6. Querying 0050 raises StockNotSupportedError
    with pytest.raises(StockNotSupportedError) as exc_info:
        service.lookup_stocks("0050")
    assert exc_info.value.code == "STOCK_NOT_SUPPORTED"
    assert "目前只支援上市、上櫃普通股" in exc_info.value.message


# --- 3. Search and Ranking Tests ---

def test_search_ranking():
    """Verify exact match and prefix match precedence, and maximum 10 results."""
    repo = CacheRepository(db_path=":memory:")
    df = pd.DataFrame([
        {"stock_id": "2317", "stock_name": "鴻海", "type": "twse", "industry_category": "其他電子業", "is_supported": 1},
        {"stock_id": "2354", "stock_name": "鴻準", "type": "twse", "industry_category": "其他電子業", "is_supported": 1},
        {"stock_id": "3046", "stock_name": "建達鴻", "type": "tpex", "industry_category": "電子通路業", "is_supported": 1},
        {"stock_id": "2330", "stock_name": "台積電", "type": "twse", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "2454", "stock_name": "聯發科", "type": "twse", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "0050", "stock_name": "元大台灣50", "type": "twse", "industry_category": "ETF", "is_supported": 0},
    ])
    repo.upsert_stock_info(df)

    # Search for '鴻':
    # Prefix matches ('鴻海', '鴻準') MUST rank before middle contains ('建達鴻')
    results = repo.search_stocks("鴻", limit=10)
    names = [r["stock_name"] for r in results]
    assert "鴻海" in names
    assert "鴻準" in names
    assert names.index("鴻海") < names.index("建達鴻")
    assert names.index("鴻準") < names.index("建達鴻")

    # Search for exact code '2330': first result must be 2330
    res_code = repo.search_stocks("2330", limit=10)
    assert res_code[0]["stock_id"] == "2330"
    assert res_code[0]["stock_name"] == "台積電"
    assert res_code[0]["market"] == "上市"


# --- 4. API End-to-End Tests (Task 3.2) ---

@pytest.fixture
def api_client():
    """FastAPI TestClient with in-memory DataService prepopulated with fixture data."""
    repo = CacheRepository(db_path=":memory:")
    client = MockStockInfoClient()
    service = DataService(client=client, repo=repo)
    # Populate cache
    service.sync_stock_info(force=True)

    app.dependency_overrides[get_data_service] = lambda: service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_api_stock_lookup_2330(api_client):
    """GET /api/stocks?q=2330 returns 台積電 as first result with market 上市."""
    resp = api_client.get("/api/stocks?q=2330")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert first["stock_id"] == "2330"
    assert first["stock_name"] == "台積電"
    assert first["market"] == "上市"


def test_api_stock_lookup_hong(api_client):
    """GET /api/stocks?q=鴻 returns <= 10 items with prefix matches ranked first."""
    resp = api_client.get("/api/stocks?q=鴻")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert 1 <= len(data) <= 10
    # Every item must match '鴻' in stock_name or stock_id
    assert all("鴻" in item["stock_name"] or "鴻" in item["stock_id"] for item in data)
    # Check that prefix matches appear before middle contains if both exist
    prefix_indices = [i for i, item in enumerate(data) if item["stock_name"].startswith("鴻")]
    contains_indices = [i for i, item in enumerate(data) if not item["stock_name"].startswith("鴻")]
    if prefix_indices and contains_indices:
        assert max(prefix_indices) < min(contains_indices)


def test_api_stock_lookup_no_result(api_client):
    """GET /api/stocks?q=查無此股票xyz returns 200 with an empty list."""
    resp = api_client.get("/api/stocks?q=查無此股票xyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


def test_api_stock_lookup_0050_unsupported(api_client):
    """GET /api/stocks?q=0050 returns 400 with STOCK_NOT_SUPPORTED hint."""
    resp = api_client.get("/api/stocks?q=0050")
    assert resp.status_code == 400
    err = resp.json()
    assert err["code"] == "STOCK_NOT_SUPPORTED"
    assert "目前只支援上市、上櫃普通股" in err["message"]
    assert "目前只支援上市、上櫃普通股" in err["hint"]


def test_api_stock_lookup_empty_query(api_client):
    """GET /api/stocks with empty or missing q returns 200 with empty list."""
    resp1 = api_client.get("/api/stocks")
    assert resp1.status_code == 200
    assert resp1.json() == []

    resp2 = api_client.get("/api/stocks?q=   ")
    assert resp2.status_code == 200
    assert resp2.json() == []
