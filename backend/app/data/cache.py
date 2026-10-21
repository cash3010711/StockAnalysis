"""SQLite cache repository for Taiwan stock market data."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd

from app.data.publication import get_daily_effective_date

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.db"


class CacheRepository:
    """Manages SQLite tables, schema migrations, and point-in-time data storage."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)

        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def close(self):
        """Close connection if in-memory."""
        if self._mem_conn is not None:
            self._mem_conn.close()
            self._mem_conn = None

    def _init_schema(self):
        """Create all required tables with primary keys and effective_date columns."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Daily K-bar (OHLCV)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_k (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                money REAL,
                spread REAL,
                turnover REAL,
                effective_date TEXT NOT NULL,
                PRIMARY KEY (stock_id, date)
            )
            """)

            # 2. Institutional Investors
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS institutional_investors (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                foreign_buy REAL DEFAULT 0,
                foreign_sell REAL DEFAULT 0,
                investment_trust_buy REAL DEFAULT 0,
                investment_trust_sell REAL DEFAULT 0,
                dealer_buy REAL DEFAULT 0,
                dealer_sell REAL DEFAULT 0,
                effective_date TEXT NOT NULL,
                PRIMARY KEY (stock_id, date)
            )
            """)

            # 3. Margin & Short Sale
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS margin_short (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                margin_purchase_buy REAL DEFAULT 0,
                margin_purchase_sell REAL DEFAULT 0,
                margin_purchase_balance REAL DEFAULT 0,
                short_sale_buy REAL DEFAULT 0,
                short_sale_sell REAL DEFAULT 0,
                short_sale_balance REAL DEFAULT 0,
                effective_date TEXT NOT NULL,
                PRIMARY KEY (stock_id, date)
            )
            """)

            # 4. Monthly Revenue
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_revenue (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                revenue_year INTEGER NOT NULL,
                revenue_month INTEGER NOT NULL,
                revenue REAL DEFAULT 0,
                actual_publication_date TEXT,
                effective_date TEXT NOT NULL,
                PRIMARY KEY (stock_id, date)
            )
            """)

            # 5. Quarterly Financial Statements
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quarterly_financials (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                eps REAL DEFAULT 0,
                debt_ratio REAL DEFAULT 0,
                effective_date TEXT NOT NULL,
                PRIMARY KEY (stock_id, date)
            )
            """)

            # 6. Stock Info (stock lookup cache)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_info (
                stock_id TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                type TEXT,
                industry_category TEXT,
                updated_at TEXT NOT NULL
            )
            """)

            # 7. Fetch Log (tracks incremental sync)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetch_log (
                stock_id TEXT NOT NULL,
                dataset TEXT NOT NULL,
                last_fetched_date TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (stock_id, dataset)
            )
            """)

            conn.commit()

    # --- Fetch Log Operations ---

    def get_fetch_log(self, stock_id: str, dataset: str) -> Optional[str]:
        """Return the last_fetched_date for a given stock and dataset."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_fetched_date FROM fetch_log WHERE stock_id = ? AND dataset = ?",
                (stock_id, dataset),
            )
            row = cursor.fetchone()
            return row["last_fetched_date"] if row else None

    def update_fetch_log(self, stock_id: str, dataset: str, last_fetched_date: str):
        """Update last_fetched_date in fetch_log."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO fetch_log (stock_id, dataset, last_fetched_date, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(stock_id, dataset) DO UPDATE SET
                    last_fetched_date = excluded.last_fetched_date,
                    updated_at = excluded.updated_at
                """,
                (stock_id, dataset, last_fetched_date, now_str),
            )
            conn.commit()

    # --- Upsert Operations ---

    def upsert_daily_k(self, stock_id: str, df: pd.DataFrame):
        """Upsert daily K records into daily_k table."""
        if df.empty:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                d = str(r["date"])
                eff = str(r.get("effective_date", get_daily_effective_date(d)))
                cursor.execute(
                    """
                    INSERT INTO daily_k (
                        stock_id, date, open, high, low, close, volume, money, spread, turnover, effective_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_id, date) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume,
                        money = excluded.money,
                        spread = excluded.spread,
                        turnover = excluded.turnover,
                        effective_date = excluded.effective_date
                    """,
                    (
                        stock_id, d,
                        float(r.get("open", 0.0)),
                        float(r.get("high", 0.0)),
                        float(r.get("low", 0.0)),
                        float(r.get("close", 0.0)),
                        float(r.get("volume", 0.0)),
                        float(r.get("money", 0.0)),
                        float(r.get("spread", 0.0)),
                        float(r.get("turnover", 0.0)),
                        eff,
                    ),
                )
            conn.commit()

    def upsert_institutional_investors(self, stock_id: str, df: pd.DataFrame):
        """Upsert institutional investors records into institutional_investors table.

        Supports both raw records (with 'name', 'buy', 'sell') and already pivoted records.
        """
        if df.empty:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if "name" in df.columns and "buy" in df.columns:
                # Group raw rows by date and aggregate
                for d, group in df.groupby("date"):
                    d_str = str(d)
                    foreign_buy = 0.0
                    foreign_sell = 0.0
                    trust_buy = 0.0
                    trust_sell = 0.0
                    dealer_buy = 0.0
                    dealer_sell = 0.0

                    for _, row in group.iterrows():
                        name = str(row.get("name", ""))
                        b = float(row.get("buy", 0.0) or 0.0)
                        s = float(row.get("sell", 0.0) or 0.0)

                        if "foreign" in name.lower():
                            foreign_buy += b
                            foreign_sell += s
                        elif "trust" in name.lower():
                            trust_buy += b
                            trust_sell += s
                        elif "dealer" in name.lower():
                            dealer_buy += b
                            dealer_sell += s

                    eff = get_daily_effective_date(d_str)
                    cursor.execute(
                        """
                        INSERT INTO institutional_investors (
                            stock_id, date, foreign_buy, foreign_sell,
                            investment_trust_buy, investment_trust_sell,
                            dealer_buy, dealer_sell, effective_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(stock_id, date) DO UPDATE SET
                            foreign_buy = excluded.foreign_buy,
                            foreign_sell = excluded.foreign_sell,
                            investment_trust_buy = excluded.investment_trust_buy,
                            investment_trust_sell = excluded.investment_trust_sell,
                            dealer_buy = excluded.dealer_buy,
                            dealer_sell = excluded.dealer_sell,
                            effective_date = excluded.effective_date
                        """,
                        (
                            stock_id, d_str,
                            foreign_buy, foreign_sell,
                            trust_buy, trust_sell,
                            dealer_buy, dealer_sell,
                            eff,
                        ),
                    )
            else:
                for _, r in df.iterrows():
                    d_str = str(r["date"])
                    eff = str(r.get("effective_date", get_daily_effective_date(d_str)))
                    cursor.execute(
                        """
                        INSERT INTO institutional_investors (
                            stock_id, date, foreign_buy, foreign_sell,
                            investment_trust_buy, investment_trust_sell,
                            dealer_buy, dealer_sell, effective_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(stock_id, date) DO UPDATE SET
                            foreign_buy = excluded.foreign_buy,
                            foreign_sell = excluded.foreign_sell,
                            investment_trust_buy = excluded.investment_trust_buy,
                            investment_trust_sell = excluded.investment_trust_sell,
                            dealer_buy = excluded.dealer_buy,
                            dealer_sell = excluded.dealer_sell,
                            effective_date = excluded.effective_date
                        """,
                        (
                            stock_id, d_str,
                            float(r.get("foreign_buy", 0.0)),
                            float(r.get("foreign_sell", 0.0)),
                            float(r.get("investment_trust_buy", 0.0)),
                            float(r.get("investment_trust_sell", 0.0)),
                            float(r.get("dealer_buy", 0.0)),
                            float(r.get("dealer_sell", 0.0)),
                            eff,
                        ),
                    )
            conn.commit()

    def upsert_margin_short(self, stock_id: str, df: pd.DataFrame):
        """Upsert margin & short sale records."""
        if df.empty:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                d_str = str(r["date"])
                eff = str(r.get("effective_date", get_daily_effective_date(d_str)))
                cursor.execute(
                    """
                    INSERT INTO margin_short (
                        stock_id, date,
                        margin_purchase_buy, margin_purchase_sell, margin_purchase_balance,
                        short_sale_buy, short_sale_sell, short_sale_balance,
                        effective_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_id, date) DO UPDATE SET
                        margin_purchase_buy = excluded.margin_purchase_buy,
                        margin_purchase_sell = excluded.margin_purchase_sell,
                        margin_purchase_balance = excluded.margin_purchase_balance,
                        short_sale_buy = excluded.short_sale_buy,
                        short_sale_sell = excluded.short_sale_sell,
                        short_sale_balance = excluded.short_sale_balance,
                        effective_date = excluded.effective_date
                    """,
                    (
                        stock_id, d_str,
                        float(r.get("margin_purchase_buy", 0.0)),
                        float(r.get("margin_purchase_sell", 0.0)),
                        float(r.get("margin_purchase_balance", 0.0)),
                        float(r.get("short_sale_buy", 0.0)),
                        float(r.get("short_sale_sell", 0.0)),
                        float(r.get("short_sale_balance", 0.0)),
                        eff,
                    ),
                )
            conn.commit()

    def upsert_monthly_revenue(self, stock_id: str, df: pd.DataFrame):
        """Upsert monthly revenue records."""
        if df.empty:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                d_str = str(r["date"])
                actual_date = r.get("actual_publication_date")
                actual_str = str(actual_date) if actual_date else None
                eff = str(r["effective_date"])
                cursor.execute(
                    """
                    INSERT INTO monthly_revenue (
                        stock_id, date, revenue_year, revenue_month, revenue,
                        actual_publication_date, effective_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_id, date) DO UPDATE SET
                        revenue_year = excluded.revenue_year,
                        revenue_month = excluded.revenue_month,
                        revenue = excluded.revenue,
                        actual_publication_date = excluded.actual_publication_date,
                        effective_date = excluded.effective_date
                    """,
                    (
                        stock_id, d_str,
                        int(r["revenue_year"]),
                        int(r["revenue_month"]),
                        float(r.get("revenue", 0.0)),
                        actual_str,
                        eff,
                    ),
                )
            conn.commit()

    def upsert_quarterly_financials(self, stock_id: str, df: pd.DataFrame):
        """Upsert quarterly financials records (EPS & Debt Ratio)."""
        if df.empty:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                d_str = str(r["date"])
                eff = str(r["effective_date"])
                cursor.execute(
                    """
                    INSERT INTO quarterly_financials (
                        stock_id, date, year, quarter, eps, debt_ratio, effective_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_id, date) DO UPDATE SET
                        year = excluded.year,
                        quarter = excluded.quarter,
                        eps = excluded.eps,
                        debt_ratio = excluded.debt_ratio,
                        effective_date = excluded.effective_date
                    """,
                    (
                        stock_id, d_str,
                        int(r["year"]),
                        int(r["quarter"]),
                        float(r.get("eps", 0.0)),
                        float(r.get("debt_ratio", 0.0)),
                        eff,
                    ),
                )
            conn.commit()

    def upsert_stock_info(self, df: pd.DataFrame):
        """Upsert stock lookup table."""
        if df.empty:
            return
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                cursor.execute(
                    """
                    INSERT INTO stock_info (
                        stock_id, stock_name, type, industry_category, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(stock_id) DO UPDATE SET
                        stock_name = excluded.stock_name,
                        type = excluded.type,
                        industry_category = excluded.industry_category,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(r["stock_id"]),
                        str(r["stock_name"]),
                        str(r.get("type", "")),
                        str(r.get("industry_category", "")),
                        now_str,
                    ),
                )
            conn.commit()

    # --- Query Operations with Point-in-time (as_of) Support ---

    def get_daily_k(self, stock_id: str, as_of_date: Optional[str] = None) -> pd.DataFrame:
        """Query daily K records, optionally restricted to effective_date <= as_of_date."""
        query = "SELECT * FROM daily_k WHERE stock_id = ?"
        params: List[Any] = [stock_id]
        if as_of_date:
            query += " AND effective_date <= ?"
            params.append(as_of_date)
        query += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_institutional_investors(
        self, stock_id: str, as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Query institutional investors records."""
        query = "SELECT * FROM institutional_investors WHERE stock_id = ?"
        params: List[Any] = [stock_id]
        if as_of_date:
            query += " AND effective_date <= ?"
            params.append(as_of_date)
        query += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_margin_short(
        self, stock_id: str, as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Query margin short records."""
        query = "SELECT * FROM margin_short WHERE stock_id = ?"
        params: List[Any] = [stock_id]
        if as_of_date:
            query += " AND effective_date <= ?"
            params.append(as_of_date)
        query += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_monthly_revenue(
        self, stock_id: str, as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Query monthly revenue records."""
        query = "SELECT * FROM monthly_revenue WHERE stock_id = ?"
        params: List[Any] = [stock_id]
        if as_of_date:
            query += " AND effective_date <= ?"
            params.append(as_of_date)
        query += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_quarterly_financials(
        self, stock_id: str, as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Query quarterly financials records."""
        query = "SELECT * FROM quarterly_financials WHERE stock_id = ?"
        params: List[Any] = [stock_id]
        if as_of_date:
            query += " AND effective_date <= ?"
            params.append(as_of_date)
        query += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def as_of(self, stock_id: str, date: str) -> Dict[str, pd.DataFrame]:
        """Return point-in-time view of all datasets for stock_id as of the given date.

        Guarantees effective_date <= date for all datasets.
        """
        return {
            "daily_k": self.get_daily_k(stock_id, as_of_date=date),
            "institutional_investors": self.get_institutional_investors(stock_id, as_of_date=date),
            "margin_short": self.get_margin_short(stock_id, as_of_date=date),
            "monthly_revenue": self.get_monthly_revenue(stock_id, as_of_date=date),
            "quarterly_financials": self.get_quarterly_financials(stock_id, as_of_date=date),
        }
