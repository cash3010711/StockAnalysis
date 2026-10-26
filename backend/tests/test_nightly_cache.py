import pytest
from app.data.cache import CacheRepository


@pytest.fixture
def repo():
    r = CacheRepository(":memory:")
    yield r
    r.close()


def test_nightly_plan_save_and_get(repo):
    items = [
        {
            "stock_id": "2330",
            "stock_name": "台積電",
            "market": "TWSE",
            "strategy": "突破均線",
            "win_rate": 0.72,
            "trade_count": 25,
            "entry_price": 1020.0,
            "stop_loss": 980.0,
            "take_profit": 1100.0,
            "holding_days": 5,
            "risk_reward_ratio": 2.0,
            "close_price": 1015.0,
            "volume": 25000000,
            "reason": "L1, L2, L3 通過",
        },
        {
            "stock_id": "2454",
            "stock_name": "聯發科",
            "market": "TWSE",
            "strategy": "布林通道突破",
            "win_rate": 0.65,
            "trade_count": 18,
            "entry_price": 1300.0,
            "stop_loss": 1250.0,
            "take_profit": 1400.0,
            "holding_days": 10,
            "risk_reward_ratio": 2.0,
            "close_price": 1290.0,
            "volume": 8000000,
            "reason": "L1, L2 通過",
        },
    ]

    plan_id = repo.save_nightly_plan(
        scan_date="2026-10-26",
        items=items,
        plan_id="plan_test_01",
        total_candidates=50,
        notes="測試掃描",
    )
    assert plan_id == "plan_test_01"

    # Fetch by ID
    plan = repo.get_nightly_plan_by_id("plan_test_01")
    assert plan is not None
    assert plan["plan_id"] == "plan_test_01"
    assert plan["scan_date"] == "2026-10-26"
    assert plan["total_candidates"] == 50
    assert plan["selected_count"] == 2
    assert plan["notes"] == "測試掃描"
    assert len(plan["items"]) == 2

    # Check ordered by win_rate descending
    assert plan["items"][0]["stock_id"] == "2330"
    assert plan["items"][0]["win_rate"] == 0.72
    assert plan["items"][1]["stock_id"] == "2454"
    assert plan["items"][1]["win_rate"] == 0.65


def test_nightly_plan_latest_and_date(repo):
    # Save plan 1 on 2026-10-25
    repo.save_nightly_plan(
        scan_date="2026-10-25",
        items=[{"stock_id": "2330", "stock_name": "台積電", "market": "TWSE", "strategy": "S1", "close_price": 1000.0, "entry_price": 1000.0, "stop_loss": 980.0, "take_profit": 1050.0}],
        plan_id="plan_day1",
    )

    # Save plan 2 on 2026-10-26
    repo.save_nightly_plan(
        scan_date="2026-10-26",
        items=[{"stock_id": "2317", "stock_name": "鴻海", "market": "TWSE", "strategy": "S2", "close_price": 150.0, "entry_price": 150.0, "stop_loss": 145.0, "take_profit": 160.0}],
        plan_id="plan_day2",
    )

    # Latest should be plan_day2
    latest = repo.get_latest_nightly_plan()
    assert latest is not None
    assert latest["plan_id"] == "plan_day2"
    assert latest["scan_date"] == "2026-10-26"

    # Query by date
    day1_plan = repo.get_nightly_plan_by_date("2026-10-25")
    assert day1_plan is not None
    assert day1_plan["plan_id"] == "plan_day1"

    non_existent = repo.get_nightly_plan_by_date("2020-01-01")
    assert non_existent is None


def test_nightly_plan_list_and_delete(repo):
    repo.save_nightly_plan(scan_date="2026-10-25", items=[], plan_id="p1")
    repo.save_nightly_plan(scan_date="2026-10-26", items=[], plan_id="p2")

    plans = repo.list_nightly_plans()
    assert len(plans) == 2

    # Delete p1
    deleted = repo.delete_nightly_plan("p1")
    assert deleted is True

    plans_after = repo.list_nightly_plans()
    assert len(plans_after) == 1
    assert plans_after[0]["plan_id"] == "p2"
