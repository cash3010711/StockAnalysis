"""Unit tests for AI Advice streaming API endpoint."""
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.main import app
from tests.test_analysis_api import _setup_service_with_data


@pytest.fixture
def test_setup():
    repo = CacheRepository(db_path=":memory:")
    service = _setup_service_with_data(repo, stock_id="2330", stock_name="台積電", n_days=50)
    app.dependency_overrides[get_data_service] = lambda: service
    client = TestClient(app)
    try:
        yield repo, service, client
    finally:
        app.dependency_overrides.clear()


def parse_sse_events(response_text: str):
    """Helper to parse SSE lines into JSON objects."""
    events = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload_str = line[len("data: "):]
            events.append(json.loads(payload_str))
    return events


def test_ai_advice_invalid_stock(test_setup):
    _, _, client = test_setup
    resp = client.get("/api/analysis/invalid/ai-advice")
    assert resp.status_code == 400
    assert resp.json()["code"] == "STOCK_NOT_SUPPORTED"


def test_ai_advice_missing_api_key(test_setup):
    _, _, client = test_setup
    with patch("app.api.analysis.has_gemini_api_key", return_value=False):
        resp = client.get("/api/analysis/2330/ai-advice")
        assert resp.status_code == 400
        data = resp.json()
        assert data["code"] == "GEMINI_API_KEY_MISSING"
        assert "尚未設定 Gemini API 金鑰" in data["message"]


def test_ai_advice_stream_and_cache(test_setup):
    repo, service, client = test_setup
    sync_res = service.sync_stock("2330")
    eval_date = sync_res.latest_k_date

    chunks = ["### 1. 【進場適宜度判定】\n", "目前均線多頭排列，可偏多操作。\n", "### 2. 【關鍵進出場價位規劃】\n"]

    with patch("app.api.analysis.has_gemini_api_key", return_value=True), \
         patch("app.api.analysis.stream_ai_advice", return_value=iter(chunks)) as mock_stream:
        resp = client.get("/api/analysis/2330/ai-advice")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = parse_sse_events(resp.text)
        assert len(events) == 4
        assert events[0] == {"text": chunks[0], "delta": chunks[0], "cached": False, "done": False}
        assert events[1] == {"text": chunks[1], "delta": chunks[1], "cached": False, "done": False}
        assert events[2] == {"text": chunks[2], "delta": chunks[2], "cached": False, "done": False}
        assert events[3] == {"text": "", "delta": "", "cached": False, "done": True}

        # Check cached in DB
        cached = repo.get_ai_advice("2330", eval_date)
        assert cached is not None
        assert cached["content"] == "".join(chunks)
        assert mock_stream.called


def test_ai_advice_cache_hit(test_setup):
    repo, service, client = test_setup
    sync_res = service.sync_stock("2330")
    eval_date = sync_res.latest_k_date

    # Seed cache
    cached_content = "既有當日快取戰略：觀望"
    repo.save_ai_advice("2330", eval_date, cached_content)

    with patch("app.api.analysis.stream_ai_advice") as mock_stream:
        resp = client.get("/api/analysis/2330/ai-advice")
        assert resp.status_code == 200
        events = parse_sse_events(resp.text)
        assert len(events) == 1
        assert events[0] == {
            "text": cached_content,
            "delta": cached_content,
            "cached": True,
            "done": True,
        }
        # Gemini stream must NOT be called on cache hit
        assert not mock_stream.called


def test_ai_advice_force_refresh(test_setup):
    repo, service, client = test_setup
    sync_res = service.sync_stock("2330")
    eval_date = sync_res.latest_k_date

    # Seed cache with old content
    repo.save_ai_advice("2330", eval_date, "舊的快取內容")

    new_chunks = ["強制刷新後的最新分析：拉回加碼"]

    with patch("app.api.analysis.has_gemini_api_key", return_value=True), \
         patch("app.api.analysis.stream_ai_advice", return_value=iter(new_chunks)) as mock_stream:
        resp = client.get("/api/analysis/2330/ai-advice?force=true")
        assert resp.status_code == 200
        events = parse_sse_events(resp.text)
        assert len(events) == 2
        assert events[0]["delta"] == new_chunks[0]
        assert events[0]["cached"] is False
        assert events[1]["done"] is True

        # Check DB was overwritten with new content
        updated = repo.get_ai_advice("2330", eval_date)
        assert updated is not None
        assert updated["content"] == "強制刷新後的最新分析：拉回加碼"
        assert mock_stream.called


def test_ai_advice_stream_runtime_error(test_setup):
    _, _, client = test_setup

    def broken_stream(*args, **kwargs):
        yield "正常片段"
        raise RuntimeError("API quota exceeded mid-stream")

    with patch("app.api.analysis.has_gemini_api_key", return_value=True), \
         patch("app.api.analysis.stream_ai_advice", side_effect=broken_stream):
        resp = client.get("/api/analysis/2330/ai-advice")
        assert resp.status_code == 200
        events = parse_sse_events(resp.text)
        assert len(events) == 2
        assert events[0]["delta"] == "正常片段"
        assert events[1]["code"] == "AI_GENERATION_FAILED"
        assert events[1]["done"] is True
