"""Unit tests for watchlist table schema and CRUD operations in CacheRepository."""
import sqlite3
import pytest

from app.data.cache import CacheRepository


@pytest.fixture
def repo():
    """Create in-memory CacheRepository."""
    r = CacheRepository(db_path=":memory:")
    yield r
    r.close()


def test_watchlist_table_created(repo):
    """Verify watchlist table is initialized with expected columns."""
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(watchlist)")
        cols = {row["name"]: row["type"] for row in cursor.fetchall()}

    assert "stock_id" in cols
    assert "stock_name" in cols
    assert "added_date" in cols
    assert "added_price" in cols
    assert "notes" in cols
    assert "created_at" in cols


def test_watchlist_crud_operations(repo):
    """Verify add, query, and delete operations on watchlist."""
    # Initially empty
    assert repo.get_watchlist() == []
    assert repo.get_watchlist_item("2330") is None
    assert not repo.is_in_watchlist("2330")

    # Add item
    item = repo.add_watchlist_item(
        stock_id="2330",
        stock_name="台積電",
        added_date="2026-10-27",
        added_price=1050.0,
        notes="長期核心持股",
    )
    assert item["stock_id"] == "2330"
    assert item["stock_name"] == "台積電"
    assert item["added_date"] == "2026-10-27"
    assert item["added_price"] == 1050.0
    assert item["notes"] == "長期核心持股"
    assert item["created_at"] is not None

    # Query item
    fetched = repo.get_watchlist_item("2330")
    assert fetched is not None
    assert fetched["stock_id"] == "2330"
    assert repo.is_in_watchlist("2330")

    # List items
    all_items = repo.get_watchlist()
    assert len(all_items) == 1
    assert all_items[0]["stock_id"] == "2330"

    # Delete item
    deleted = repo.delete_watchlist_item("2330")
    assert deleted is True
    assert repo.get_watchlist() == []
    assert not repo.is_in_watchlist("2330")

    # Deleting non-existent item returns False
    deleted_again = repo.delete_watchlist_item("2330")
    assert deleted_again is False


def test_watchlist_prevent_duplicate_insert(repo):
    """Verify attempting to insert an already tracked stock_id raises IntegrityError."""
    repo.add_watchlist_item(
        stock_id="2454",
        stock_name="聯發科",
        added_date="2026-10-27",
        added_price=1300.0,
    )

    # Duplicate insert should raise sqlite3.IntegrityError due to PRIMARY KEY
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_watchlist_item(
            stock_id="2454",
            stock_name="聯發科",
            added_date="2026-10-27",
            added_price=1320.0,
        )
