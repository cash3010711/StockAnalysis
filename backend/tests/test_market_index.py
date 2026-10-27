"""Unit tests for market index caching and incremental sync."""

from unittest.mock import MagicMock
import pandas as pd
import pytest

from app.data.cache import CacheRepository
from app.data.exceptions import FinMindQuotaExceededError
from app.data.service import DataService


@pytest.fixture
def temp_cache(tmp_path):
    """Provide a fresh temporary SQLite cache."""
    db_file = tmp_path / "test_cache.db"
    repo = CacheRepository(db_path=db_file)
    yield repo
    repo.close()


def test_first_sync_market_index(temp_cache):
    """Scenario: 首次同步加權指數 -> 成功存入快取並記錄 fetch_log."""
    mock_client = MagicMock()
    sample_df = pd.DataFrame({
        "index_id": ["TAIEX", "TAIEX"],
        "date": ["2024-01-02", "2024-01-03"],
        "open": [17800.0, 17850.0],
        "high": [17900.0, 17950.0],
        "low": [17750.0, 17800.0],
        "close": [17853.0, 17912.0],
        "volume": [2500000000.0, 2600000000.0],
    })
    mock_client.get_market_index.return_value = sample_df

    service = DataService(client=mock_client, repo=temp_cache)
    df, warnings = service.sync_market_index("TAIEX")

    assert len(df) == 2
    assert "2024-01-02" in df["date"].values
    assert temp_cache.get_fetch_log("TAIEX", "market_index") is not None
    assert len(warnings) == 0


def test_incremental_sync_market_index(temp_cache):
    """Scenario: 增量同步加權指數 -> 只向 client 請求最後日期之後的資料."""
    mock_client = MagicMock()
    # First sync
    initial_df = pd.DataFrame({
        "index_id": ["TAIEX"],
        "date": ["2024-01-02"],
        "open": [17800.0],
        "high": [17900.0],
        "low": [17750.0],
        "close": [17853.0],
        "volume": [2500000000.0],
    })
    temp_cache.upsert_market_index("TAIEX", initial_df)
    temp_cache.update_fetch_log("TAIEX", "market_index", "2024-01-02")

    # Incremental update returned by client
    inc_df = pd.DataFrame({
        "index_id": ["TAIEX"],
        "date": ["2024-01-03"],
        "open": [17850.0],
        "high": [17950.0],
        "low": [17800.0],
        "close": [17912.0],
        "volume": [2600000000.0],
    })
    mock_client.get_market_index.return_value = inc_df

    service = DataService(client=mock_client, repo=temp_cache)
    df, warnings = service.sync_market_index("TAIEX")

    # Start date passed to client should be 2024-01-03
    mock_client.get_market_index.assert_called_once()
    call_args = mock_client.get_market_index.call_args[1]
    assert call_args["start_date"] == "2024-01-03"
    assert len(df) == 2
    assert len(warnings) == 0


def test_quota_exceeded_with_cache(temp_cache):
    """Scenario: 額度用盡但有快取 -> 沿用快取並產生警告."""
    mock_client = MagicMock()
    initial_df = pd.DataFrame({
        "index_id": ["TAIEX"],
        "date": ["2024-01-02"],
        "open": [17800.0],
        "high": [17900.0],
        "low": [17750.0],
        "close": [17853.0],
        "volume": [2500000000.0],
    })
    temp_cache.upsert_market_index("TAIEX", initial_df)
    temp_cache.update_fetch_log("TAIEX", "market_index", "2024-01-02")

    mock_client.get_market_index.side_effect = FinMindQuotaExceededError("Quota exceeded")

    service = DataService(client=mock_client, repo=temp_cache)
    df, warnings = service.sync_market_index("TAIEX")

    assert len(df) == 1
    assert any("API 額度已用盡" in w for w in warnings)


def test_quota_exceeded_without_cache(temp_cache):
    """Scenario: 額度用盡且無快取 -> 拋出 FinMindQuotaExceededError."""
    mock_client = MagicMock()
    mock_client.get_market_index.side_effect = FinMindQuotaExceededError("Quota exceeded")

    service = DataService(client=mock_client, repo=temp_cache)
    with pytest.raises(FinMindQuotaExceededError):
        service.sync_market_index("TAIEX")
