"""Unit tests for point-in-time correctness of as_of data view."""
import pandas as pd
import pytest

from app.data.cache import CacheRepository


@pytest.fixture
def populated_repo():
    """Create CacheRepository with multi-date and multi-dataset test records."""
    repo = CacheRepository(db_path=":memory:")
    stock_id = "2330"

    # Daily K
    df_k = pd.DataFrame([
        {"date": "2024-09-19", "open": 900.0, "high": 910.0, "low": 895.0, "close": 905.0, "volume": 10000, "effective_date": "2024-09-19"},
        {"date": "2024-09-20", "open": 905.0, "high": 915.0, "low": 900.0, "close": 912.0, "volume": 12000, "effective_date": "2024-09-20"},
        {"date": "2024-10-11", "open": 950.0, "high": 960.0, "low": 945.0, "close": 955.0, "volume": 15000, "effective_date": "2024-10-11"},
    ])
    repo.upsert_daily_k(stock_id, df_k)

    # Monthly Revenue:
    # 1. August 2024 revenue (effective 2024-09-10)
    # 2. September 2024 revenue (effective 2024-10-10)
    df_rev = pd.DataFrame([
        {
            "date": "2024-09-01",
            "revenue_year": 2024,
            "revenue_month": 8,
            "revenue": 250866000000,
            "actual_publication_date": "2024-09-10",
            "effective_date": "2024-09-10",
        },
        {
            "date": "2024-10-01",
            "revenue_year": 2024,
            "revenue_month": 9,
            "revenue": 251873000000,
            "actual_publication_date": "2024-10-10",
            "effective_date": "2024-10-10",
        },
    ])
    repo.upsert_monthly_revenue(stock_id, df_rev)

    # Quarterly Financials:
    # 2024 Q1 (ended 2024-03-31, statutory effective date 2024-05-15)
    # 2024 Q2 (ended 2024-06-30, statutory effective date 2024-08-14)
    df_q = pd.DataFrame([
        {"date": "2024-03-31", "year": 2024, "quarter": 1, "eps": 8.70, "debt_ratio": 35.0, "effective_date": "2024-05-15"},
        {"date": "2024-06-30", "year": 2024, "quarter": 2, "eps": 9.56, "debt_ratio": 34.5, "effective_date": "2024-08-14"},
    ])
    repo.upsert_quarterly_financials(stock_id, df_q)

    return repo


def test_as_of_monthly_revenue_visibility(populated_repo):
    """Scenario 2.6: On 9/20 cannot see September revenue; on 10/11 can see September revenue."""
    stock_id = "2330"

    # View as of 2024-09-20
    view_0920 = populated_repo.as_of(stock_id, "2024-09-20")
    rev_0920 = view_0920["monthly_revenue"]

    # Only August revenue (effective 2024-09-10) should be visible
    assert len(rev_0920) == 1
    assert rev_0920.iloc[0]["revenue_month"] == 8
    assert (rev_0920["revenue_month"] == 9).sum() == 0  # September revenue is NOT visible!

    # View as of 2024-10-11
    view_1011 = populated_repo.as_of(stock_id, "2024-10-11")
    rev_1011 = view_1011["monthly_revenue"]

    # Both August and September revenues (effective 2024-10-10) are now visible!
    assert len(rev_1011) == 2
    months_visible = set(rev_1011["revenue_month"].tolist())
    assert months_visible == {8, 9}


def test_as_of_daily_k_no_future_bars(populated_repo):
    """Daily K bars after as_of_date must not be visible in as_of view."""
    stock_id = "2330"

    view_0920 = populated_repo.as_of(stock_id, "2024-09-20")
    k_0920 = view_0920["daily_k"]

    assert len(k_0920) == 2
    assert "2024-10-11" not in k_0920["date"].tolist()


def test_as_of_quarterly_financials_statutory_cutoff(populated_repo):
    """Quarterly financials must not be visible before their statutory effective date."""
    stock_id = "2330"

    # On 2024-05-10, Q1 (effective 2024-05-15) is not yet effective
    view_0510 = populated_repo.as_of(stock_id, "2024-05-10")
    assert len(view_0510["quarterly_financials"]) == 0

    # On 2024-05-16, Q1 is effective
    view_0516 = populated_repo.as_of(stock_id, "2024-05-16")
    assert len(view_0516["quarterly_financials"]) == 1
    assert view_0516["quarterly_financials"].iloc[0]["quarter"] == 1
