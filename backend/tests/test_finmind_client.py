"""Unit tests for FinMindClient mocking HTTP responses."""
import json
from pathlib import Path
import httpx
import pytest

from app.data.exceptions import (
    FinMindApiError,
    FinMindQuotaExceededError,
    FinMindTokenMissingError,
)
from app.data.finmind_client import FinMindClient

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "finmind"


def load_fixture(filename: str):
    path = FIXTURE_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"msg": "success", "status": 200, "data": []}


def test_token_missing_raises_exception():
    """Client with empty token should raise FinMindTokenMissingError when querying protected datasets."""
    client = FinMindClient(token="")
    with pytest.raises(FinMindTokenMissingError) as exc_info:
        client.get_daily_k("2330", "2024-01-01")
    assert exc_info.value.code == "TOKEN_MISSING"
    assert "尚未設定 FinMind token" in str(exc_info.value)


def test_quota_exceeded_http_402():
    """Client should raise FinMindQuotaExceededError when receiving HTTP 402."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            json={"msg": "Requests reach the upper limit. https://finmindtrade.com/", "status": 402},
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = FinMindClient(token="mock_token", http_client=http_client)

    with pytest.raises(FinMindQuotaExceededError) as exc_info:
        client.get_daily_k("2330", "2024-01-01")
    assert exc_info.value.code == "QUOTA_EXCEEDED"
    assert "API 額度已用盡" in str(exc_info.value)


def test_quota_exceeded_status_in_body():
    """Client should raise FinMindQuotaExceededError if status=402 is returned in JSON body with HTTP 200."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"msg": "Requests reach the upper limit.", "status": 402, "data": []},
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = FinMindClient(token="mock_token", http_client=http_client)

    with pytest.raises(FinMindQuotaExceededError):
        client.get_margin_short("2330", "2024-01-01")


def test_illegal_token_raises_token_missing():
    """Illegal token message should be converted to FinMindTokenMissingError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"msg": "Token is illegal.", "status": 400},
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = FinMindClient(token="invalid_token", http_client=http_client)

    with pytest.raises(FinMindTokenMissingError):
        client.get_daily_k("2330", "2024-01-01")


def test_successful_get_daily_k_with_fallback():
    """Successful fetch using real fixture or mock data."""
    fixture_data = load_fixture("daily_price.json")

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        dataset = params.get("dataset")
        if dataset == "TaiwanStockPriceAdj":
            # Simulate free user getting 400 for Adj, triggering fallback to TaiwanStockPrice
            return httpx.Response(
                400,
                json={"msg": "Your level is free. Please update your user level.", "status": 400},
            )
        elif dataset == "TaiwanStockPrice":
            return httpx.Response(200, json=fixture_data)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = FinMindClient(token="mock_token", http_client=http_client)

    df = client.get_daily_k("2330", "2024-01-02", "2024-01-05")
    assert not df.empty
    assert "close" in df.columns
    assert "high" in df.columns
    assert "volume" in df.columns
    assert len(df) == len(fixture_data.get("data", []))


def test_successful_get_institutional_investors():
    """Verify institutional investors parsing."""
    fixture_data = load_fixture("institutional.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture_data)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = FinMindClient(token="mock_token", http_client=http_client)

    df = client.get_institutional_investors("2330", "2024-01-02", "2024-01-03")
    assert not df.empty
    assert "name" in df.columns
    assert "buy" in df.columns
    assert "sell" in df.columns


def test_successful_get_quarterly_financials():
    """Verify quarterly financials combined from financial statements and balance sheet."""
    fs_data = load_fixture("financial_statements.json")
    bs_data = load_fixture("balance_sheet.json")

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        ds = params.get("dataset")
        if ds == "TaiwanStockFinancialStatements":
            return httpx.Response(200, json=fs_data)
        elif ds == "TaiwanStockBalanceSheet":
            return httpx.Response(200, json=bs_data)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = FinMindClient(token="mock_token", http_client=http_client)

    df = client.get_quarterly_financials("2330", "2023-01-01", "2023-12-31")
    assert not df.empty
    assert "eps" in df.columns
    assert "debt_ratio" in df.columns
    assert "effective_date" in df.columns
    # Check 2023 Q1
    q1 = df[df["quarter"] == 1].iloc[0]
    assert q1["year"] == 2023
    assert q1["eps"] == 7.98
    assert abs(q1["debt_ratio"] - 38.70) < 0.1
    assert q1["effective_date"] == "2023-05-15"
