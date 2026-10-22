"""Unit tests for market scanner pool resolution and filtering."""
from unittest.mock import MagicMock
import pandas as pd
import pytest

from app.analysis import params
from app.analysis.scanner import (
    TAIWAN_50_STOCKS,
    ScanFilterConfig,
    resolve_scan_pool,
)
from app.data.cache import CacheRepository
from app.data.service import DataService


@pytest.fixture
def service():
    """Create DataService with in-memory CacheRepository and mocked FinMindClient."""
    repo = CacheRepository(db_path=":memory:")
    client = MagicMock()
    client.get_stock_info.return_value = pd.DataFrame()
    return DataService(client=client, repo=repo)


def _seed_sample_stocks(service: DataService):
    df_info = pd.DataFrame([
        {"stock_id": "2330", "stock_name": "台積電", "type": "twse", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "2317", "stock_name": "鴻海", "type": "twse", "industry_category": "其他電子業", "is_supported": 1},
        {"stock_id": "2454", "stock_name": "聯發科", "type": "twse", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "6488", "stock_name": "環球晶", "type": "tpex", "industry_category": "半導體業", "is_supported": 1},
        {"stock_id": "8069", "stock_name": "元太", "type": "tpex", "industry_category": "光電業", "is_supported": 1},
        {"stock_id": "0050", "stock_name": "元大台灣50", "type": "twse", "industry_category": "ETF", "is_supported": 0},
    ])
    service.repo.upsert_stock_info(df_info)

    df_k = pd.DataFrame([
        {"date": "2024-01-02", "open": 590.0, "high": 595.0, "low": 588.0, "close": 593.0, "volume": 20000, "effective_date": "2024-01-02"}
    ])
    service.repo.upsert_daily_k("2330", df_k)
    service.repo.upsert_daily_k("6488", df_k)
    service.repo.upsert_daily_k("8069", df_k)


def test_taiwan_50_stocks_list():
    """Verify TAIWAN_50_STOCKS has 50 valid common stock entries."""
    assert len(TAIWAN_50_STOCKS) == 50
    ids = [s["stock_id"] for s in TAIWAN_50_STOCKS]
    assert len(set(ids)) == 50
    assert "2330" in ids
    assert "2317" in ids
    assert "2454" in ids
    for item in TAIWAN_50_STOCKS:
        assert len(item["stock_id"]) == 4 and item["stock_id"].isdigit()
        assert item["stock_name"]
        assert item["market"] in ("上市", "上櫃")
        assert item["type"] in ("twse", "tpex")
        assert item["industry_category"]


def test_scan_filter_config_defaults():
    """Verify ScanFilterConfig defaults to all 5 strategies when empty."""
    cfg = ScanFilterConfig(strategies=[])
    assert cfg.pool == "cached"
    assert cfg.require_fundamental is True
    assert cfg.require_chips is True
    assert cfg.strategies == params.ALL_STRATEGIES


def test_resolve_scan_pool_cached_and_industry(service):
    """Verify 'cached' pool returns only stocks with cached daily_k and respects industry filter."""
    _seed_sample_stocks(service)

    pool_cached = resolve_scan_pool(service, ScanFilterConfig(pool="cached"))
    assert [s["stock_id"] for s in pool_cached] == ["2330", "6488", "8069"]
    assert pool_cached[0]["stock_name"] == "台積電"
    assert pool_cached[1]["market"] == "上櫃"

    pool_cached_semi = resolve_scan_pool(
        service, ScanFilterConfig(pool="cached", industry_category="半導體業")
    )
    assert [s["stock_id"] for s in pool_cached_semi] == ["2330", "6488"]


def test_resolve_scan_pool_tw50_and_industry(service):
    """Verify 'tw50' pool returns 50 stocks or filters by industry category."""
    pool_tw50 = resolve_scan_pool(service, ScanFilterConfig(pool="tw50"))
    assert len(pool_tw50) == 50

    pool_tw50_semi = resolve_scan_pool(
        service, ScanFilterConfig(pool="tw50", industry_category="半導體業")
    )
    assert len(pool_tw50_semi) > 0
    assert all(s["industry_category"] == "半導體業" for s in pool_tw50_semi)
    assert "2330" in [s["stock_id"] for s in pool_tw50_semi]


def test_resolve_scan_pool_all_twse_tpex_industry(service):
    """Verify 'all', 'twse', 'tpex', and 'industry' pools and limit slicing."""
    _seed_sample_stocks(service)

    pool_all = resolve_scan_pool(service, ScanFilterConfig(pool="all"))
    assert [s["stock_id"] for s in pool_all] == ["2317", "2330", "2454", "6488", "8069"]

    pool_twse = resolve_scan_pool(service, ScanFilterConfig(pool="twse"))
    assert [s["stock_id"] for s in pool_twse] == ["2317", "2330", "2454"]

    pool_tpex = resolve_scan_pool(service, ScanFilterConfig(pool="tpex"))
    assert [s["stock_id"] for s in pool_tpex] == ["6488", "8069"]

    pool_ind = resolve_scan_pool(
        service, ScanFilterConfig(pool="industry", industry_category="半導體業")
    )
    assert [s["stock_id"] for s in pool_ind] == ["2330", "2454", "6488"]

    pool_twse_semi = resolve_scan_pool(
        service, ScanFilterConfig(pool="twse", industry_category="半導體業")
    )
    assert [s["stock_id"] for s in pool_twse_semi] == ["2330", "2454"]

    pool_limited = resolve_scan_pool(service, ScanFilterConfig(pool="all", limit=2))
    assert [s["stock_id"] for s in pool_limited] == ["2317", "2330"]
