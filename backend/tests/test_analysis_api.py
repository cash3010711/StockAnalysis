"""Tests for Analysis API endpoint (Tasks 6.1 and 6.2)."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analysis import params
from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.exceptions import (
    FinMindQuotaExceededError,
    FinMindTokenMissingError,
    InsufficientDataError,
    StockNotSupportedError,
)
from app.data.finmind_client import FinMindClient
from app.data.service import DataService
from app.main import app

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "finmind"


def load_fixture_data(filename: str):
    path = FIXTURE_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"msg": "success", "status": 200, "data": []}


def _generate_test_stock_data(
    stock_id: str = "2330",
    n_days: int = 400,
    chips_pass: bool = True,
    fund_pass: bool = True,
    end_date: str = None,
):
    """Generate mock historical dataset for testing analysis and backtest."""
    if end_date is None:
        target_d = DataService.get_target_trade_date()
        end_date = target_d.isoformat()

    dates = pd.date_range(end=end_date, periods=n_days, freq="B").strftime("%Y-%m-%d").tolist()

    np.random.seed(42)
    closes = [100.0]
    for _ in range(1, n_days):
        pct = np.random.normal(0.0005, 0.015)
        closes.append(round(closes[-1] * (1.0 + pct), 2))

    opens = [round(c * (1.0 + np.random.normal(0, 0.005)), 2) for c in closes]
    highs = [max(o, c) + round(abs(np.random.normal(1.0, 0.5)), 2) for o, c in zip(opens, closes)]
    lows = [min(o, c) - round(abs(np.random.normal(1.0, 0.5)), 2) for o, c in zip(opens, closes)]
    volumes = [int(abs(np.random.normal(2000, 500))) for _ in range(n_days)]

    daily_k = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "effective_date": dates,
    })

    # Fundamentals
    yoy_mult = 1.15 if fund_pass else 0.85
    eps_val = 2.5 if fund_pass else -1.0
    debt_val = 40.0 if fund_pass else 75.0

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

    f_buy = 200_000 if chips_pass else 0
    f_sell = 0 if chips_pass else 500_000

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


def _setup_service_with_data(
    repo: CacheRepository,
    stock_id: str = "2330",
    stock_name: str = "台積電",
    n_days: int = 400,
    fund_pass: bool = True,
    chips_pass: bool = True,
    token: str = "mock_token",
) -> DataService:
    """Helper to populate in-memory CacheRepository with data and return DataService."""
    daily_k, rev, qf, inst, margin = _generate_test_stock_data(
        stock_id=stock_id,
        n_days=n_days,
        fund_pass=fund_pass,
        chips_pass=chips_pass,
    )

    repo.upsert_daily_k(stock_id, daily_k)
    repo.upsert_monthly_revenue(stock_id, rev)
    repo.upsert_quarterly_financials(stock_id, qf)
    repo.upsert_institutional_investors(stock_id, inst)
    repo.upsert_margin_short(stock_id, margin)

    target_date = DataService.get_target_trade_date().isoformat()
    for ds in ["daily_k", "monthly_revenue", "quarterly_financials", "institutional_investors", "margin_short"]:
        repo.update_fetch_log(stock_id, ds, target_date)

    # Insert stock_info
    info_df = pd.DataFrame([{
        "stock_id": stock_id,
        "stock_name": stock_name,
        "type": "twse",
        "industry_category": "半導體業",
        "is_supported": 1,
    }])
    repo.upsert_stock_info(info_df)

    client = FinMindClient(token=token)
    return DataService(client=client, repo=repo)


# =========================================================================
# 6.1 分析 API 結構與功能測試
# =========================================================================

def test_api_analysis_success_structure():
    """GET /api/analysis/{stock_id} returns 200 with complete analysis, backtest, and OHLCV structure."""
    repo = CacheRepository(db_path=":memory:")
    service = _setup_service_with_data(repo, stock_id="2330", stock_name="台積電", n_days=400)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 200

        data = resp.json()

        # Top-level fields
        assert data["stock_id"] == "2330"
        assert data["stock_name"] == "台積電"
        assert isinstance(data["evaluation_date"], str)
        assert len(data["evaluation_date"]) == 10
        assert "僅供個人研究參考，非投資建議" in data["disclaimer"]
        assert isinstance(data["warnings"], list)

        # Fundamental layer
        fund = data["fundamental"]
        assert isinstance(fund["passed"], bool)
        assert fund["passed"] is True
        assert fund["revenue_yoy"] is not None
        assert fund["eps_4q_sum"] is not None
        assert fund["debt_ratio"] is not None
        assert isinstance(fund["reason"], str)

        # Chips layer
        chips = data["chips"]
        assert isinstance(chips["passed"], bool)
        assert chips["passed"] is True
        assert chips["foreign_trust_net_buy_10d"] is not None
        assert chips["margin_increase_rate_10d"] is not None
        assert isinstance(chips["reason"], str)

        # Strategies
        strategies = data["strategies"]
        assert isinstance(strategies, list)
        assert len(strategies) == len(params.ALL_STRATEGIES)

        strategy_names = [s["strategy_name"] for s in strategies]
        for expected_name in params.ALL_STRATEGIES:
            assert expected_name in strategy_names

        for strat in strategies:
            assert strat["status"] in ("進場", "觀望")
            assert strat["action"] in ("BUY", "WAIT")
            assert isinstance(strat["technical_signal"], bool)
            assert strat["can_backtest"] is True
            assert strat["backtest_message"] is None

            # Three-layer stats
            tl = strat["three_layer_stats"]
            assert tl is not None
            assert "total_trades" in tl
            assert "win_trades" in tl
            assert "win_rate" in tl
            assert "expected_value" in tl
            assert "max_drawdown" in tl
            assert "insufficient_sample" in tl
            assert "equity_curve" in tl
            assert isinstance(tl["equity_curve"], list)

            # Tech-only stats
            to = strat["tech_only_stats"]
            assert to is not None
            assert "total_trades" in to
            assert "win_trades" in to

            # Trades list
            assert isinstance(strat["three_layer_trades"], list)
            assert isinstance(strat["tech_only_trades"], list)

            if strat["status"] == "進場":
                assert strat["entry_price"] is not None
                assert strat["stop_loss"] is not None
                assert strat["take_profit"] is not None
                assert strat["max_holding_days"] == 20
                assert strat["entry_price"] > strat["stop_loss"]
                assert strat["take_profit"] > strat["entry_price"]

        # OHLCV bars
        ohlcv = data["ohlcv"]
        assert isinstance(ohlcv, list)
        assert len(ohlcv) == 400
        first_bar = ohlcv[0]
        assert "date" in first_bar
        assert "open" in first_bar
        assert "high" in first_bar
        assert "low" in first_bar
        assert "close" in first_bar
        assert "volume" in first_bar
        assert first_bar["high"] >= first_bar["low"]

        # Institutional sequence (recent 30 days)
        institutional = data["institutional"]
        assert isinstance(institutional, list)
        assert len(institutional) == 30
        first_inst = institutional[0]
        assert "date" in first_inst
        assert "foreign_net" in first_inst
        assert "investment_trust_net" in first_inst
        assert "dealer_net" in first_inst
        assert "total_net" in first_inst
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_with_recorded_fixtures():
    """Verify analysis API using recorded FinMind fixture data."""
    stock_info_fixture = load_fixture_data("stock_info.json")

    repo = CacheRepository(db_path=":memory:")
    # Populate stock_info from real fixture
    info_df = pd.DataFrame(stock_info_fixture["data"])
    info_df["is_supported"] = 1
    repo.upsert_stock_info(info_df)

    service = _setup_service_with_data(repo, stock_id="2330", stock_name="台積電", n_days=300)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock_id"] == "2330"
        assert data["stock_name"] == "台積電"
        assert len(data["strategies"]) == 5
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_history_less_than_one_year():
    """When stock has >= 35 days but < 365 days, backtest cannot run, returns message without win rate."""
    repo = CacheRepository(db_path=":memory:")
    # 60 business days is ~3 months (< 1 year)
    service = _setup_service_with_data(repo, stock_id="2330", n_days=60)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 200
        data = resp.json()

        # Warnings should note history length
        assert any("歷史資料僅" in w for w in data["warnings"])

        # Today analysis still operates
        assert data["fundamental"]["passed"] is True
        assert len(data["strategies"]) == 5

        # All strategies have can_backtest=False and message
        for strat in data["strategies"]:
            assert strat["can_backtest"] is False
            assert strat["backtest_message"] == "歷史資料不足 1 年，無法回測"
            assert strat["three_layer_stats"] is None
            assert strat["tech_only_stats"] is None
            assert strat["three_layer_trades"] == []
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_quota_exceeded_with_cache_returns_warning():
    """When API quota is exceeded but cache exists, response is 200 with warning."""
    repo = CacheRepository(db_path=":memory:")
    daily_k, rev, qf, inst, margin = _generate_test_stock_data("2330", n_days=300)

    repo.upsert_daily_k("2330", daily_k)
    repo.upsert_monthly_revenue("2330", rev)
    repo.upsert_quarterly_financials("2330", qf)
    repo.upsert_institutional_investors("2330", inst)
    repo.upsert_margin_short("2330", margin)
    # fetch_log not updated to today, so sync will attempt to fetch

    class QuotaExceededClient(FinMindClient):
        def __init__(self):
            super().__init__(token="mock_token")

        def get_daily_k(self, *args, **kwargs):
            raise FinMindQuotaExceededError()

    client_mock = QuotaExceededClient()
    service = DataService(client=client_mock, repo=repo)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 200
        data = resp.json()
        assert any("API 額度已用盡" in w for w in data["warnings"])
        assert len(data["strategies"]) == 5
    finally:
        app.dependency_overrides.clear()


# =========================================================================
# 6.2 統一錯誤格式測試（TOKEN_MISSING, QUOTA_EXCEEDED, STOCK_NOT_SUPPORTED, INSUFFICIENT_HISTORY）
# =========================================================================

def test_api_analysis_error_token_missing():
    """GET /api/analysis/{stock_id} with missing token returns 400 and TOKEN_MISSING error."""
    repo = CacheRepository(db_path=":memory:")
    client_mock = FinMindClient(token="")
    service = DataService(client=client_mock, repo=repo)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 400
        err = resp.json()
        assert err["code"] == "TOKEN_MISSING"
        assert "尚未設定 FinMind token" in err["message"]
        assert "FINMIND_TOKEN" in err["hint"]
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_error_quota_exceeded_no_cache():
    """GET /api/analysis/{stock_id} when quota exceeded and no cache returns 400 and QUOTA_EXCEEDED."""
    repo = CacheRepository(db_path=":memory:")

    class QuotaExceededClient(FinMindClient):
        def __init__(self):
            super().__init__(token="mock_token")

        def get_daily_k(self, *args, **kwargs):
            raise FinMindQuotaExceededError()

    client_mock = QuotaExceededClient()
    service = DataService(client=client_mock, repo=repo)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 400
        err = resp.json()
        assert err["code"] == "QUOTA_EXCEEDED"
        assert "API 額度已用盡" in err["message"]
        assert "上限" in err["hint"] or "稍後再試" in err["hint"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("unsupported_id", ["0050", "0056", "2881A", "01001T", "123456", "ABCD"])
def test_api_analysis_error_stock_not_supported(unsupported_id):
    """GET /api/analysis/{unsupported_id} returns 400 and STOCK_NOT_SUPPORTED error."""
    repo = CacheRepository(db_path=":memory:")
    service = DataService(client=FinMindClient(token="mock_token"), repo=repo)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get(f"/api/analysis/{unsupported_id}")
        assert resp.status_code == 400
        err = resp.json()
        assert err["code"] == "STOCK_NOT_SUPPORTED"
        assert "目前只支援上市、上櫃普通股" in err["message"]
        assert "目前只支援上市、上櫃普通股" in err["hint"]
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_error_insufficient_history_too_few_days():
    """GET /api/analysis/{stock_id} when stock has < 35 days returns 400 and INSUFFICIENT_HISTORY error."""
    repo = CacheRepository(db_path=":memory:")
    # Only 10 days of daily_k: cannot compute 20MA or MACD
    service = _setup_service_with_data(repo, stock_id="2330", n_days=10)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 400
        err = resp.json()
        assert err["code"] == "INSUFFICIENT_HISTORY"
        assert "歷史資料不足" in err["message"]
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_ohlcv_indicator_warmup_and_values():
    """Verify OHLCV indicator series expansion: early warmup items have None, from day 20 all indicators have values."""
    repo = CacheRepository(db_path=":memory:")
    service = _setup_service_with_data(repo, stock_id="2330", stock_name="台積電", n_days=50)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 200
        data = resp.json()
        ohlcv = data["ohlcv"]
        assert len(ohlcv) == 50

        # Day 0 (first bar): all moving averages & bollinger bands must be None
        first_bar = ohlcv[0]
        assert first_bar["ma5"] is None
        assert first_bar["ma10"] is None
        assert first_bar["ma20"] is None
        assert first_bar["bb_mid"] is None
        assert first_bar["bb_upper"] is None
        assert first_bar["bb_lower"] is None

        # Day 4 (5th bar): ma5 should be present, ma10 and ma20 should still be None
        day5_bar = ohlcv[4]
        assert isinstance(day5_bar["ma5"], float)
        assert day5_bar["ma10"] is None
        assert day5_bar["ma20"] is None
        assert day5_bar["bb_mid"] is None

        # Day 9 (10th bar): ma5 and ma10 present, ma20 still None
        day10_bar = ohlcv[9]
        assert isinstance(day10_bar["ma5"], float)
        assert isinstance(day10_bar["ma10"], float)
        assert day10_bar["ma20"] is None

        # Day 19 (20th bar) onwards: all indicators present
        for bar in ohlcv[19:]:
            assert isinstance(bar["ma5"], float)
            assert isinstance(bar["ma10"], float)
            assert isinstance(bar["ma20"], float)
            assert isinstance(bar["bb_mid"], float)
            assert isinstance(bar["bb_upper"], float)
            assert isinstance(bar["bb_lower"], float)
            assert bar["bb_upper"] >= bar["bb_mid"] >= bar["bb_lower"]
            # 20MA and bb_mid are the same mathematical value
            assert bar["ma20"] == bar["bb_mid"]
        assert "需至少 35 個交易日" in err["hint"]
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_error_insufficient_history_empty_data():
    """GET /api/analysis/{stock_id} when stock has 0 days returns 400 and INSUFFICIENT_HISTORY error."""
    repo = CacheRepository(db_path=":memory:")

    class EmptyDataClient(FinMindClient):
        def __init__(self):
            super().__init__(token="mock_token")

        def get_daily_k(self, *args, **kwargs):
            return pd.DataFrame()

        def get_institutional_investors(self, *args, **kwargs):
            return pd.DataFrame()

        def get_margin_short(self, *args, **kwargs):
            return pd.DataFrame()

        def get_monthly_revenue(self, *args, **kwargs):
            return pd.DataFrame()

        def get_quarterly_financials(self, *args, **kwargs):
            return pd.DataFrame()

        def get_stock_info(self):
            return pd.DataFrame([{
                "stock_id": "9999",
                "stock_name": "無資料股",
                "type": "twse",
                "industry_category": "其他",
            }])

    client_mock = EmptyDataClient()
    service = DataService(client=client_mock, repo=repo)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/9999")
        assert resp.status_code == 400
        err = resp.json()
        assert err["code"] == "INSUFFICIENT_HISTORY"
        assert "歷史資料不足" in err["message"]
    finally:
        app.dependency_overrides.clear()


def test_api_analysis_ohlcv_indicator_warmup_and_values():
    """Verify OHLCV indicator series expansion: early warmup items have None, from day 20 all indicators have values."""
    repo = CacheRepository(db_path=":memory:")
    service = _setup_service_with_data(repo, stock_id="2330", stock_name="台積電", n_days=50)

    app.dependency_overrides[get_data_service] = lambda: service
    try:
        client = TestClient(app)
        resp = client.get("/api/analysis/2330")
        assert resp.status_code == 200
        data = resp.json()
        ohlcv = data["ohlcv"]
        assert len(ohlcv) == 50

        # Day 0 (first bar): all moving averages & bollinger bands must be None
        first_bar = ohlcv[0]
        assert first_bar["ma5"] is None
        assert first_bar["ma10"] is None
        assert first_bar["ma20"] is None
        assert first_bar["bb_mid"] is None
        assert first_bar["bb_upper"] is None
        assert first_bar["bb_lower"] is None

        # Day 4 (5th bar): ma5 should be present, ma10 and ma20 should still be None
        day5_bar = ohlcv[4]
        assert isinstance(day5_bar["ma5"], float)
        assert day5_bar["ma10"] is None
        assert day5_bar["ma20"] is None
        assert day5_bar["bb_mid"] is None

        # Day 9 (10th bar): ma5 and ma10 present, ma20 still None
        day10_bar = ohlcv[9]
        assert isinstance(day10_bar["ma5"], float)
        assert isinstance(day10_bar["ma10"], float)
        assert day10_bar["ma20"] is None

        # Day 19 (20th bar) onwards: all indicators present
        for bar in ohlcv[19:]:
            assert isinstance(bar["ma5"], float)
            assert isinstance(bar["ma10"], float)
            assert isinstance(bar["ma20"], float)
            assert isinstance(bar["bb_mid"], float)
            assert isinstance(bar["bb_upper"], float)
            assert isinstance(bar["bb_lower"], float)
            assert bar["bb_upper"] >= bar["bb_mid"] >= bar["bb_lower"]
            # 20MA and bb_mid are the same mathematical value
            assert bar["ma20"] == bar["bb_mid"]
    finally:
        app.dependency_overrides.clear()
