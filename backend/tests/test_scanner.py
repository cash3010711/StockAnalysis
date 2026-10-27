"""Unit and API tests for market scanner (Tasks 2.1, 2.2, 2.3)."""
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest

from app.analysis import params
from app.analysis.scanner import (
    TAIWAN_50_STOCKS,
    ScanFilterConfig,
    iter_scan_events,
    resolve_scan_pool,
    run_scan,
    scan_single_stock,
)
from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.exceptions import FinMindQuotaExceededError
from app.data.service import DataService
from app.main import app


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


def _generate_test_stock(
    trigger_breakout: bool = True,
    fund_pass: bool = True,
    chips_pass: bool = True,
    n_days: int = 400,
):
    """Generate mock historical dataset for a single stock."""
    dates = pd.date_range(end="2024-05-10", periods=n_days, freq="B").strftime("%Y-%m-%d").tolist()
    closes = [100.0] * n_days
    opens = [100.0] * n_days
    highs = [102.0] * n_days
    lows = [98.0] * n_days
    volumes = [1000] * n_days

    if trigger_breakout:
        # Breakout condition: close > 20d high and volume > 1.5 * 20d mean volume
        closes[-1] = 130.0
        highs[-1] = 135.0
        opens[-1] = 105.0
        lows[-1] = 104.0
        volumes[-1] = 6000

    daily_k = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "effective_date": dates,
    })

    yoy_mult = 1.20 if fund_pass else 0.80
    monthly_revenue = pd.DataFrame([
        {
            "date": f"{2021 + i // 12}-{(i % 12) + 1:02d}-01",
            "revenue_year": 2021 + i // 12,
            "revenue_month": (i % 12) + 1,
            "revenue": 100.0 * (yoy_mult ** (i // 12 + 1)),
            "effective_date": f"{2021 + i // 12}-{(i % 12) + 1:02d}-10",
        }
        for i in range(48)
    ])

    eps_val = 3.0 if fund_pass else -1.5
    debt_val = 35.0 if fund_pass else 75.0
    quarterly_financials = pd.DataFrame([
        {
            "date": f"{2021 + q // 4}-{((q % 4) + 1) * 3:02d}-01",
            "year": 2021 + q // 4,
            "quarter": (q % 4) + 1,
            "eps": eps_val,
            "debt_ratio": debt_val,
            "effective_date": f"{2021 + q // 4}-{((q % 4) + 1) * 3:02d}-15",
        }
        for q in range(16)
    ])

    f_buy = 300_000 if chips_pass else 0
    f_sell = 0 if chips_pass else 600_000
    inst_rows = []
    margin_rows = []
    for idx, d in enumerate(dates):
        inst_rows.append({
            "date": d,
            "foreign_buy": f_buy,
            "foreign_sell": f_sell,
            "investment_trust_buy": 0,
            "investment_trust_sell": 0,
            "dealer_buy": 0,
            "dealer_sell": 0,
            "effective_date": d,
        })
        margin_rows.append({"date": d, "margin_purchase_balance": 1000 + idx * 5, "effective_date": d})

    institutional_investors = pd.DataFrame(inst_rows)
    margin_short = pd.DataFrame(margin_rows)

    return daily_k, monthly_revenue, quarterly_financials, institutional_investors, margin_short


def _seed_full_stock(
    service: DataService,
    stock_id: str,
    stock_name: str,
    trigger_breakout: bool = True,
    fund_pass: bool = True,
    chips_pass: bool = True,
    industry: str = "半導體業",
    market_type: str = "twse",
):
    daily_k, rev, qf, inst, margin = _generate_test_stock(
        trigger_breakout=trigger_breakout,
        fund_pass=fund_pass,
        chips_pass=chips_pass,
    )
    service.repo.upsert_daily_k(stock_id, daily_k)
    service.repo.upsert_monthly_revenue(stock_id, rev)
    service.repo.upsert_quarterly_financials(stock_id, qf)
    service.repo.upsert_institutional_investors(stock_id, inst)
    service.repo.upsert_margin_short(stock_id, margin)

    target_date = DataService.get_target_trade_date().isoformat()
    for ds in ["daily_k", "monthly_revenue", "quarterly_financials", "institutional_investors", "margin_short"]:
        service.repo.update_fetch_log(stock_id, ds, target_date)

    info_df = pd.DataFrame([{
        "stock_id": stock_id,
        "stock_name": stock_name,
        "type": market_type,
        "industry_category": industry,
        "is_supported": 1,
    }])
    service.repo.upsert_stock_info(info_df)


# --- 1. Pool Resolution Tests ---

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


# --- 2. scan_single_stock Unit Tests ---

def test_scan_single_stock_short_circuits_when_no_technical_signal(service):
    """Verify scan_single_stock returns None immediately when no strategy triggers."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=False)
    matched, quota_hit = scan_single_stock(service, "2330", ScanFilterConfig())
    assert matched is None
    assert quota_hit is False


def test_scan_single_stock_three_layer_pass(service):
    """Verify scan_single_stock returns full matched details and backtest stats when passing."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True, fund_pass=True, chips_pass=True)
    matched, quota_hit = scan_single_stock(service, "2330", ScanFilterConfig())

    assert matched is not None
    assert quota_hit is False
    assert matched["stock_id"] == "2330"
    assert matched["stock_name"] == "台積電"
    assert matched["close"] == 130.0
    assert params.STRATEGY_BREAKOUT_20D in matched["triggered_strategies"]
    assert matched["fundamental_passed"] is True
    assert matched["chips_passed"] is True
    assert matched["entry_price"] == 130.0
    assert matched["stop_loss"] is not None and matched["stop_loss"] < 130.0
    assert matched["take_profit"] is not None and matched["take_profit"] > 130.0
    assert matched["max_holding_days"] == 20
    assert matched["best_strategy_name"] == params.STRATEGY_BREAKOUT_20D


def test_scan_single_stock_fundamental_filter_toggle(service):
    """Verify require_fundamental filter filters out failing stock or keeps it when disabled."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True, fund_pass=False, chips_pass=True)

    # When fundamental is required, it must be filtered out
    matched_req, _ = scan_single_stock(service, "2330", ScanFilterConfig(require_fundamental=True))
    assert matched_req is None

    # When fundamental is relaxed, it is included with fundamental_passed=False
    matched_opt, _ = scan_single_stock(service, "2330", ScanFilterConfig(require_fundamental=False))
    assert matched_opt is not None
    assert matched_opt["fundamental_passed"] is False
    assert matched_opt["chips_passed"] is True


def test_scan_single_stock_chips_filter_toggle(service):
    """Verify require_chips filter filters out failing stock or keeps it when disabled."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True, fund_pass=True, chips_pass=False)

    # When chips is required, it must be filtered out
    matched_req, _ = scan_single_stock(service, "2330", ScanFilterConfig(require_chips=True))
    assert matched_req is None

    # When chips is relaxed, it is included with chips_passed=False
    matched_opt, _ = scan_single_stock(service, "2330", ScanFilterConfig(require_chips=False))
    assert matched_opt is not None
    assert matched_opt["chips_passed"] is False
    assert matched_opt["fundamental_passed"] is True


def test_scan_single_stock_strategy_filtering(service):
    """Verify stock is filtered out if triggered strategy is not in config.strategies."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True, fund_pass=True, chips_pass=True)

    # Filter for only MA Pullback -> breakout stock should not match
    matched_diff, _ = scan_single_stock(
        service,
        "2330",
        ScanFilterConfig(strategies=[params.STRATEGY_MA_PULLBACK]),
    )
    assert matched_diff is None

    # Filter for Breakout -> matches
    matched_same, _ = scan_single_stock(
        service,
        "2330",
        ScanFilterConfig(strategies=[params.STRATEGY_BREAKOUT_20D]),
    )
    assert matched_same is not None


# --- 3. iter_scan_events & Circuit Breaker Tests ---

def test_iter_scan_events_emits_all_events(service):
    """Verify iter_scan_events emits start, match, progress, and done events."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)
    _seed_full_stock(service, "2317", "鴻海", trigger_breakout=False)

    events = list(iter_scan_events(service, ScanFilterConfig(pool="cached")))
    event_types = [e["event"] for e in events]

    assert "start" in event_types
    assert "progress" in event_types
    assert "match" in event_types
    assert "done" in event_types

    start_ev = next(e for e in events if e["event"] == "start")
    assert start_ev["total"] == 2

    done_ev = next(e for e in events if e["event"] == "done")
    assert done_ev["total"] == 2
    assert done_ev["scanned"] == 2
    assert done_ev["matched_count"] == 1
    assert done_ev["quota_exceeded"] is False


def test_iter_scan_events_quota_circuit_breaker(service):
    """Verify that when FinMind quota is hit, subsequent stocks bypass sync and use local cache."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)
    _seed_full_stock(service, "2317", "鴻海", trigger_breakout=True)

    # First stock triggers quota exceeded, second stock should NOT call sync_stock
    service.sync_stock = MagicMock(side_effect=[
        FinMindQuotaExceededError(message="Quota exceeded"),
        Exception("Should not be called!"),
    ])

    events = list(iter_scan_events(service, ScanFilterConfig(pool="cached", sync_latest=True)))

    # Only one sync_stock call was made
    assert service.sync_stock.call_count == 1

    done_ev = next(e for e in events if e["event"] == "done")
    assert done_ev["quota_exceeded"] is True
    assert len(done_ev["warnings"]) > 0
    assert "額度已達上限" in done_ev["warnings"][0]
    # Both stocks were still processed from local cache!
    assert done_ev["scanned"] == 2
    assert done_ev["matched_count"] == 2


# --- 4. API Endpoints Tests ---

@pytest.fixture
def api_client(service):
    """TestClient with dependency override for DataService."""
    app.dependency_overrides[get_data_service] = lambda: service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_api_scanner_options(api_client, service):
    """Verify GET /api/scanner/options returns valid structure and default configuration."""
    _seed_full_stock(service, "2330", "台積電")

    res = api_client.get("/api/scanner/options")
    assert res.status_code == 200
    data = res.json()

    assert "pools" in data
    assert any(p["id"] == "cached" for p in data["pools"])
    assert any(p["id"] == "tw50" for p in data["pools"])
    assert "strategies" in data
    assert len(data["strategies"]) == 5
    assert data["cached_count"] >= 1
    assert "defaults" in data
    assert data["defaults"]["pool"] == "cached"


def test_api_scanner_run(api_client, service):
    """Verify POST /api/scanner/run returns full batch scan results."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)
    _seed_full_stock(service, "2317", "鴻海", trigger_breakout=False)

    payload = {
        "pool": "cached",
        "sync_latest": False,
        "require_fundamental": True,
        "require_chips": True,
    }
    res = api_client.post("/api/scanner/run", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 2
    assert data["scanned"] == 2
    assert data["matched_count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["stock_id"] == "2330"


def test_api_scanner_stream(api_client, service):
    """Verify POST /api/scanner/stream returns NDJSON lines with event stream."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)

    payload = {
        "pool": "cached",
        "sync_latest": False,
    }
    res = api_client.post("/api/scanner/stream", json=payload)
    assert res.status_code == 200
    assert "application/x-ndjson" in res.headers.get("content-type", "")

    lines = [json.loads(line) for line in res.text.strip().split("\n") if line.strip()]
    ev_types = [l["event"] for l in lines]
    assert "start" in ev_types
    assert "match" in ev_types
    assert "progress" in ev_types
    assert "done" in ev_types


def test_scanner_require_above_ma60(service):
    """Verify require_above_ma60 filters out stocks where close < 60MA."""
    # Seed 2330 with close=130 > ma60 ~ 100.5
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)

    # Config with require_above_ma60=True should match 2330
    cfg_pass = ScanFilterConfig(
        pool="cached",
        require_above_ma60=True,
        require_fundamental=False,
        require_chips=False,
    )
    res_pass, _ = scan_single_stock(service, "2330", cfg_pass)
    assert res_pass is not None
    assert res_pass["stock_id"] == "2330"

    # Now drop the last close below 60MA
    daily_k = service.repo.get_daily_k("2330")
    daily_k.loc[daily_k.index[-1], "close"] = 50.0  # Well below 60MA (~100)
    service.repo.upsert_daily_k("2330", daily_k)

    # Should now be filtered out when require_above_ma60 is True
    res_fail, _ = scan_single_stock(service, "2330", cfg_pass)
    assert res_fail is None

    # But without require_above_ma60, if breakout was still triggered (or if we relax), it wouldn't fail on ma60
    cfg_no_ma = ScanFilterConfig(
        pool="cached",
        require_above_ma60=False,
        require_fundamental=False,
        require_chips=False,
    )
    # Restore close above 20d high
    daily_k.loc[daily_k.index[-1], "close"] = 90.0  # below 60MA (~100), but let's test ma60 filtering specifically
    service.repo.upsert_daily_k("2330", daily_k)
    res_fail_ma60, _ = scan_single_stock(service, "2330", cfg_pass)
    assert res_fail_ma60 is None


def test_scanner_factor_score_fields_populated(service):
    """Verify factor scoring fields are present in matched scanner output."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)
    cfg = ScanFilterConfig(
        pool="cached",
        require_fundamental=True,
        require_chips=True,
    )
    matched, _ = scan_single_stock(service, "2330", cfg)
    assert matched is not None
    assert "factor_score" in matched
    assert isinstance(matched["factor_score"], (int, float))
    assert 0.0 <= matched["factor_score"] <= 100.0
    assert "factor_decile" in matched
    assert 1 <= matched["factor_decile"] <= 10
    assert "historical_hit_rate" in matched
    assert "historical_lift" in matched
    assert "triggered_factors" in matched
    assert isinstance(matched["triggered_factors"], list)


def test_run_scan_sorts_by_factor_score(service):
    """Verify run_scan orders results by factor_score descending."""
    _seed_full_stock(service, "2330", "台積電", trigger_breakout=True)
    _seed_full_stock(service, "2317", "鴻海", trigger_breakout=True)

    cfg = ScanFilterConfig(
        pool="cached",
        require_fundamental=True,
        require_chips=True,
    )
    result = run_scan(service, cfg)
    results = result["results"]
    assert len(results) >= 2
    scores = [r["factor_score"] for r in results]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


