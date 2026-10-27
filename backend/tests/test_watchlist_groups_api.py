import pytest
from fastapi.testclient import TestClient
import pandas as pd

from app.api.stocks import get_data_service
from app.data.cache import CacheRepository
from app.data.service import DataService
from app.main import app


@pytest.fixture
def test_client():
    repo = CacheRepository(db_path=":memory:")
    service = DataService(repo=repo)

    # Seed stock_info and daily_k for 2330 and 2454
    df_info = pd.DataFrame([
        {
            "stock_id": "2330",
            "stock_name": "台積電",
            "type": "twse",
            "industry_category": "半導體業",
            "is_supported": 1,
        },
        {
            "stock_id": "2454",
            "stock_name": "聯發科",
            "type": "twse",
            "industry_category": "半導體業",
            "is_supported": 1,
        },
    ])
    repo.upsert_stock_info(df_info)

    df_k = pd.DataFrame([
        {
            "stock_id": "2330",
            "date": "2026-10-27",
            "open": 1000.0,
            "high": 1010.0,
            "low": 995.0,
            "close": 1005.0,
            "volume": 20000,
            "money": 20100000.0,
            "spread": 5.0,
            "turnover": 4000,
            "effective_date": "2026-10-27",
        },
        {
            "stock_id": "2454",
            "date": "2026-10-27",
            "open": 1200.0,
            "high": 1220.0,
            "low": 1190.0,
            "close": 1210.0,
            "volume": 10000,
            "money": 12100000.0,
            "spread": 10.0,
            "turnover": 2000,
            "effective_date": "2026-10-27",
        },
    ])
    repo.upsert_daily_k("2330", df_k[df_k["stock_id"] == "2330"])
    repo.upsert_daily_k("2454", df_k[df_k["stock_id"] == "2454"])

    app.dependency_overrides[get_data_service] = lambda: service
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    repo.close()


def test_watchlist_groups_endpoints_crud(test_client):
    # 1. GET groups initially empty
    resp = test_client.get("/api/watchlist/groups")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. POST create group
    resp_create = test_client.post("/api/watchlist/groups", json={"name": "科技波段"})
    assert resp_create.status_code == 201
    group_data = resp_create.json()
    assert group_data["name"] == "科技波段"
    group_id = group_data["id"]

    # Validation: empty name
    resp_empty = test_client.post("/api/watchlist/groups", json={"name": "  "})
    assert resp_empty.status_code == 400

    # Validation: duplicate name
    resp_dup = test_client.post("/api/watchlist/groups", json={"name": "科技波段"})
    assert resp_dup.status_code == 400

    # Create second group
    resp_create2 = test_client.post("/api/watchlist/groups", json={"name": "高息防禦"})
    assert resp_create2.status_code == 201
    group_id2 = resp_create2.json()["id"]

    # 3. GET groups
    resp_list = test_client.get("/api/watchlist/groups")
    assert resp_list.status_code == 200
    names = [g["name"] for g in resp_list.json()]
    assert names == ["科技波段", "高息防禦"]

    # 4. DELETE group
    resp_del = test_client.delete(f"/api/watchlist/groups/{group_id2}")
    assert resp_del.status_code == 200
    assert resp_del.json()["success"] is True

    # DELETE non-existent group
    resp_del_404 = test_client.delete(f"/api/watchlist/groups/{group_id2}")
    assert resp_del_404.status_code == 404


def test_watchlist_stock_groups_assignment_and_filtering(test_client):
    # Add stocks to watchlist
    test_client.post("/api/watchlist", json={"stock_id": "2330"})
    test_client.post("/api/watchlist", json={"stock_id": "2454"})

    # Create groups
    g1 = test_client.post("/api/watchlist/groups", json={"name": "AI概念"}).json()
    g2 = test_client.post("/api/watchlist/groups", json={"name": "權值龍頭"}).json()
    gid1, gid2 = g1["id"], g2["id"]

    # PUT groups for stock not in watchlist -> 404
    resp_404 = test_client.put("/api/watchlist/9999/groups", json={"group_ids": [gid1]})
    assert resp_404.status_code == 404

    # PUT non-existent group -> 404
    resp_grp_404 = test_client.put("/api/watchlist/2330/groups", json={"group_ids": [99999]})
    assert resp_grp_404.status_code == 404

    # Assign 2330 to both g1 and g2
    resp_assign = test_client.put("/api/watchlist/2330/groups", json={"group_ids": [gid1, gid2]})
    assert resp_assign.status_code == 200
    assert set(resp_assign.json()["group_ids"]) == {gid1, gid2}

    # Assign 2454 to g1
    test_client.put("/api/watchlist/2454/groups", json={"group_ids": [gid1]})

    # Verify GET /api/watchlist includes groups on each stock
    resp_wl = test_client.get("/api/watchlist")
    assert resp_wl.status_code == 200
    wl_items = {item["stock_id"]: item for item in resp_wl.json()}
    assert len(wl_items["2330"]["groups"]) == 2
    assert {g["id"] for g in wl_items["2330"]["groups"]} == {gid1, gid2}
    assert len(wl_items["2454"]["groups"]) == 1
    assert wl_items["2454"]["groups"][0]["id"] == gid1

    # Verify GET /api/watchlist?group_id={gid2} returns only 2330
    resp_filter_g2 = test_client.get(f"/api/watchlist?group_id={gid2}")
    assert resp_filter_g2.status_code == 200
    assert len(resp_filter_g2.json()) == 1
    assert resp_filter_g2.json()[0]["stock_id"] == "2330"

    # DELETE /api/watchlist/{stock_id}/groups/{group_id}
    resp_del_link = test_client.delete(f"/api/watchlist/2330/groups/{gid2}")
    assert resp_del_link.status_code == 200
    assert resp_del_link.json()["success"] is True

    # 2330 now only has g1
    resp_check = test_client.get(f"/api/watchlist?group_id={gid2}")
    assert len(resp_check.json()) == 0

    # Stock 2330 still in public pool
    resp_all = test_client.get("/api/watchlist")
    assert len(resp_all.json()) == 2
