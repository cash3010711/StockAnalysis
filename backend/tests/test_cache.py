"""Unit tests for SQLite CacheRepository and schemas."""
import pandas as pd
import pytest

from app.data.cache import CacheRepository


@pytest.fixture
def repo():
    """Create in-memory CacheRepository for clean test isolation."""
    return CacheRepository(db_path=":memory:")


def test_schema_tables_and_columns(repo):
    """Verify all required tables, primary keys, and effective_date columns exist."""
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "daily_k",
            "institutional_investors",
            "margin_short",
            "monthly_revenue",
            "quarterly_financials",
            "stock_info",
            "fetch_log",
        }
        assert expected_tables.issubset(tables)

        # Check primary keys for data tables
        data_tables = [
            "daily_k",
            "institutional_investors",
            "margin_short",
            "monthly_revenue",
            "quarterly_financials",
        ]
        for tbl in data_tables:
            cursor.execute(f"PRAGMA table_info({tbl})")
            columns = {row["name"]: row for row in cursor.fetchall()}
            assert "stock_id" in columns
            assert "date" in columns
            assert "effective_date" in columns
            # pk column in table_info is > 0 for primary key columns
            assert columns["stock_id"]["pk"] > 0
            assert columns["date"]["pk"] > 0


def test_duplicate_writes_do_not_produce_duplicate_rows(repo):
    """Verify that repeated upserts do not insert duplicate rows for (stock_id, date)."""
    stock_id = "2330"

    # 1. Daily K duplicate write
    df_k = pd.DataFrame([
        {"date": "2024-01-02", "open": 590.0, "high": 593.0, "low": 589.0, "close": 593.0, "volume": 20000, "effective_date": "2024-01-02"},
        {"date": "2024-01-03", "open": 584.0, "high": 585.0, "low": 576.0, "close": 578.0, "volume": 30000, "effective_date": "2024-01-03"},
    ])
    repo.upsert_daily_k(stock_id, df_k)
    # Upsert again with updated close
    df_k_updated = pd.DataFrame([
        {"date": "2024-01-02", "open": 590.0, "high": 593.0, "low": 589.0, "close": 595.0, "volume": 20000, "effective_date": "2024-01-02"},
    ])
    repo.upsert_daily_k(stock_id, df_k_updated)

    res_k = repo.get_daily_k(stock_id)
    assert len(res_k) == 2  # Still 2 rows, not 3!
    assert res_k.loc[res_k["date"] == "2024-01-02", "close"].iloc[0] == 595.0

    # 2. Institutional Investors duplicate write
    df_inst = pd.DataFrame([
        {"date": "2024-01-02", "name": "Foreign_Investor", "buy": 1000, "sell": 500},
        {"date": "2024-01-02", "name": "Investment_Trust", "buy": 200, "sell": 100},
    ])
    repo.upsert_institutional_investors(stock_id, df_inst)
    repo.upsert_institutional_investors(stock_id, df_inst)
    res_inst = repo.get_institutional_investors(stock_id)
    assert len(res_inst) == 1  # 1 aggregated row for 2024-01-02
    assert res_inst.iloc[0]["foreign_buy"] == 1000
    assert res_inst.iloc[0]["investment_trust_buy"] == 200

    # 3. Monthly Revenue duplicate write
    df_rev = pd.DataFrame([
        {"date": "2024-01-01", "revenue_year": 2023, "revenue_month": 12, "revenue": 1000000, "effective_date": "2024-01-10"},
    ])
    repo.upsert_monthly_revenue(stock_id, df_rev)
    repo.upsert_monthly_revenue(stock_id, df_rev)
    res_rev = repo.get_monthly_revenue(stock_id)
    assert len(res_rev) == 1

    # 4. Quarterly Financials duplicate write
    df_q = pd.DataFrame([
        {"date": "2023-03-31", "year": 2023, "quarter": 1, "eps": 7.98, "debt_ratio": 38.7, "effective_date": "2023-05-15"},
    ])
    repo.upsert_quarterly_financials(stock_id, df_q)
    repo.upsert_quarterly_financials(stock_id, df_q)
    res_q = repo.get_quarterly_financials(stock_id)
    assert len(res_q) == 1


def test_fetch_log_tracking(repo):
    """Verify fetch_log record insertion and updating."""
    stock_id = "2330"
    assert repo.get_fetch_log(stock_id, "daily_k") is None

    repo.update_fetch_log(stock_id, "daily_k", "2024-01-05")
    assert repo.get_fetch_log(stock_id, "daily_k") == "2024-01-05"

    repo.update_fetch_log(stock_id, "daily_k", "2024-01-10")
    assert repo.get_fetch_log(stock_id, "daily_k") == "2024-01-10"
