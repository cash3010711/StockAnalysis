import sqlite3
import pytest
from app.data.cache import CacheRepository


@pytest.fixture
def repo():
    r = CacheRepository(db_path=":memory:")
    yield r
    r.close()


def test_watchlist_groups_crud(repo: CacheRepository):
    # 1. Create groups
    g1 = repo.create_watchlist_group("科技核心")
    assert g1["id"] is not None
    assert g1["name"] == "科技核心"

    g2 = repo.create_watchlist_group("高股息")
    assert g2["id"] is not None
    assert g2["name"] == "高股息"

    # Duplicate name should raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_watchlist_group("科技核心")

    # Empty name should raise ValueError
    with pytest.raises(ValueError):
        repo.create_watchlist_group("   ")

    # 2. Get groups
    groups = repo.get_watchlist_groups()
    assert len(groups) == 2
    assert [g["name"] for g in groups] == ["科技核心", "高股息"]

    # 3. Get single group
    single = repo.get_watchlist_group(g1["id"])
    assert single is not None
    assert single["name"] == "科技核心"

    by_name = repo.get_watchlist_group_by_name("高股息")
    assert by_name is not None
    assert by_name["id"] == g2["id"]

    # 4. Update group
    updated = repo.update_watchlist_group(g1["id"], "AI科技龍頭")
    assert updated is not None
    assert updated["name"] == "AI科技龍頭"

    # 5. Delete group
    deleted = repo.delete_watchlist_group(g2["id"])
    assert deleted is True
    assert repo.get_watchlist_group(g2["id"]) is None
    assert len(repo.get_watchlist_groups()) == 1


def test_watchlist_stock_groups_association_and_filter(repo: CacheRepository):
    # Add stocks to watchlist
    repo.add_watchlist_item("2330", "台積電", "2026-10-21", 980.0)
    repo.add_watchlist_item("2454", "聯發科", "2026-10-21", 1250.0)
    repo.add_watchlist_item("1101", "台泥", "2026-10-21", 35.0)

    # Create groups
    g_tech = repo.create_watchlist_group("半導體族群")
    g_div = repo.create_watchlist_group("定存領息")

    # Associate stocks with groups
    repo.add_stock_to_group("2330", g_tech["id"])
    repo.add_stock_to_group("2454", g_tech["id"])
    repo.add_stock_to_group("1101", g_div["id"])
    repo.add_stock_to_group("2330", g_div["id"])  # 2330 belongs to both groups

    # Query groups for 2330
    groups_2330 = repo.get_groups_for_stock("2330")
    assert len(groups_2330) == 2
    assert {g["id"] for g in groups_2330} == {g_tech["id"], g_div["id"]}

    # Query stocks in g_tech
    stocks_tech = repo.get_stocks_in_group(g_tech["id"])
    assert set(stocks_tech) == {"2330", "2454"}

    # Query watchlist with group filter
    wl_tech = repo.get_watchlist(group_id=g_tech["id"])
    assert len(wl_tech) == 2
    assert {item["stock_id"] for item in wl_tech} == {"2330", "2454"}

    wl_div = repo.get_watchlist(group_id=g_div["id"])
    assert len(wl_div) == 2
    assert {item["stock_id"] for item in wl_div} == {"2330", "1101"}

    # Query all (public pool)
    wl_all = repo.get_watchlist()
    assert len(wl_all) == 3

    # Remove stock from single group
    repo.remove_stock_from_group("2330", g_div["id"])
    assert len(repo.get_groups_for_stock("2330")) == 1
    assert repo.get_groups_for_stock("2330")[0]["id"] == g_tech["id"]

    # set_stock_groups
    repo.set_stock_groups("1101", [g_tech["id"]])
    assert [g["id"] for g in repo.get_groups_for_stock("1101")] == [g_tech["id"]]


def test_watchlist_groups_cascade_delete(repo: CacheRepository):
    # Add stock and group
    repo.add_watchlist_item("2330", "台積電", "2026-10-21", 980.0)
    g = repo.create_watchlist_group("核心持股")
    repo.add_stock_to_group("2330", g["id"])

    assert len(repo.get_stocks_in_group(g["id"])) == 1
    assert len(repo.get_groups_for_stock("2330")) == 1

    # 1. Delete group -> cascade removes group_items, stock remains in watchlist
    repo.delete_watchlist_group(g["id"])
    assert len(repo.get_groups_for_stock("2330")) == 0
    assert repo.is_in_watchlist("2330") is True

    # 2. Add new group, link to 2330
    g2 = repo.create_watchlist_group("波段首選")
    repo.add_stock_to_group("2330", g2["id"])
    assert len(repo.get_stocks_in_group(g2["id"])) == 1

    # Delete stock from watchlist -> cascade removes group_items, group remains
    repo.delete_watchlist_item("2330")
    assert repo.is_in_watchlist("2330") is False
    assert len(repo.get_stocks_in_group(g2["id"])) == 0
    assert repo.get_watchlist_group(g2["id"]) is not None
