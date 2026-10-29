"""SQLite cache repository for Taiwan stock market data."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd

from app.data.publication import get_daily_effective_date
from app.data.stock_filter import format_market

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
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
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
                is_supported INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL
            )
            """)

            # Ensure is_supported column exists for backward compatibility
            cursor.execute("PRAGMA table_info(stock_info)")
            stock_cols = [r[1] for r in cursor.fetchall()]
            if "is_supported" not in stock_cols:
                cursor.execute("ALTER TABLE stock_info ADD COLUMN is_supported INTEGER DEFAULT 1")

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

            # 8. Nightly Plans
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS nightly_plans (
                plan_id TEXT PRIMARY KEY,
                scan_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                total_candidates INTEGER DEFAULT 0,
                selected_count INTEGER DEFAULT 0,
                notes TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nightly_plans_scan_date ON nightly_plans(scan_date)")

            # 9. Nightly Plan Items
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS nightly_plan_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                market TEXT NOT NULL,
                strategy TEXT NOT NULL,
                win_rate REAL DEFAULT 0.0,
                trade_count INTEGER DEFAULT 0,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                holding_days INTEGER DEFAULT 5,
                risk_reward_ratio REAL DEFAULT 0.0,
                close_price REAL NOT NULL,
                volume REAL DEFAULT 0,
                reason TEXT,
                FOREIGN KEY(plan_id) REFERENCES nightly_plans(plan_id)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nightly_plan_items_plan_id ON nightly_plan_items(plan_id)")

            # 10. Watchlist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                stock_id TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                added_date TEXT NOT NULL,
                added_price REAL NOT NULL,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # 11. Watchlist Groups & Group Items
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_group_items (
                stock_id TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (stock_id, group_id),
                FOREIGN KEY (stock_id) REFERENCES watchlist(stock_id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE
            )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_group_items_group_id ON watchlist_group_items(group_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_group_items_stock_id ON watchlist_group_items(stock_id)")

            # 12. Market Index (e.g. TAIEX)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_index (
                index_id TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL DEFAULT 0,
                high REAL DEFAULT 0,
                low REAL DEFAULT 0,
                close REAL DEFAULT 0,
                volume REAL DEFAULT 0,
                PRIMARY KEY (index_id, date)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_index_id_date ON market_index(index_id, date)")

            # 13. AI Advice Cache
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_advice_cache (
                stock_id TEXT NOT NULL,
                eval_date TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (stock_id, eval_date)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_advice_cache_stock_eval ON ai_advice_cache(stock_id, eval_date)")

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

    def upsert_market_index(self, index_id: str, df: pd.DataFrame):
        """Upsert market index daily records into market_index table."""
        if df.empty:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                d = str(r["date"])
                cursor.execute(
                    """
                    INSERT INTO market_index (
                        index_id, date, open, high, low, close, volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(index_id, date) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume
                    """,
                    (
                        index_id, d,
                        float(r.get("open", 0.0)),
                        float(r.get("high", 0.0)),
                        float(r.get("low", 0.0)),
                        float(r.get("close", 0.0)),
                        float(r.get("volume", 0.0)),
                    ),
                )
            conn.commit()

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

    def upsert_stock_info(self, df: pd.DataFrame, updated_at: Optional[str] = None):
        """Upsert stock lookup table."""
        if df.empty:
            return
        now_str = updated_at or datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for _, r in df.iterrows():
                is_supp = int(r.get("is_supported", 1))
                cursor.execute(
                    """
                    INSERT INTO stock_info (
                        stock_id, stock_name, type, industry_category, is_supported, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_id) DO UPDATE SET
                        stock_name = excluded.stock_name,
                        type = excluded.type,
                        industry_category = excluded.industry_category,
                        is_supported = excluded.is_supported,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(r["stock_id"]),
                        str(r["stock_name"]),
                        str(r.get("type", "")),
                        str(r.get("industry_category", "")),
                        is_supp,
                        now_str,
                    ),
                )
            conn.commit()

    def get_stock_info_last_updated(self) -> Optional[datetime]:
        """Return the most recent updated_at timestamp in stock_info table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(updated_at) as last_updated FROM stock_info")
            row = cursor.fetchone()
            if not row or not row["last_updated"]:
                return None
            try:
                return datetime.fromisoformat(row["last_updated"])
            except ValueError:
                return None

    def is_stock_info_stale(self, max_age_days: int = 7) -> bool:
        """Check whether stock_info is missing or has not been updated within max_age_days."""
        last_updated = self.get_stock_info_last_updated()
        if last_updated is None:
            return True
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - last_updated) > timedelta(days=max_age_days)

    def get_stock_name(self, stock_id: str) -> Optional[str]:
        """Get stock_name by stock_id from stock_info table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stock_name FROM stock_info WHERE stock_id = ? LIMIT 1", (stock_id,))
            row = cursor.fetchone()
            if row and row["stock_name"]:
                return str(row["stock_name"])
            return None

    def get_stock_metadata(self, stock_id: str) -> Optional[Dict[str, str]]:
        """Get stock metadata (stock_id, stock_name, market, type, industry_category) by stock_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT stock_id, stock_name, type, industry_category
                FROM stock_info
                WHERE stock_id = ?
                LIMIT 1
                """,
                (stock_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw_type = str(row["type"] or "")
            return {
                "stock_id": str(row["stock_id"]),
                "stock_name": str(row["stock_name"] or row["stock_id"]),
                "market": format_market(raw_type),
                "type": raw_type,
                "industry_category": str(row["industry_category"] or ""),
            }

    def get_cached_stock_ids(self) -> List[str]:
        """Return sorted list of distinct supported common stock_ids that have cached daily_k data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT stock_id FROM daily_k ORDER BY stock_id ASC")
            rows = cursor.fetchall()

        result: List[str] = []
        for row in rows:
            sid = str(row["stock_id"]).strip()
            if len(sid) == 4 and sid.isdigit() and not self.is_unsupported_stock(sid):
                result.append(sid)
        return result

    def get_supported_stocks(
        self,
        industry_category: Optional[str] = None,
        market_type: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return list of supported common stocks from stock_info, optionally filtered by industry and market."""
        query = """
            SELECT stock_id, stock_name, type, industry_category
            FROM stock_info
            WHERE is_supported = 1
        """
        params: List[Any] = []

        if industry_category and industry_category.strip():
            query += " AND industry_category = ?"
            params.append(industry_category.strip())

        if market_type and market_type.strip():
            m = market_type.strip().lower()
            if m == "上市":
                m = "twse"
            elif m == "上櫃":
                m = "tpex"
            query += " AND LOWER(type) = ?"
            params.append(m)

        query += " ORDER BY stock_id ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [
            {
                "stock_id": str(r["stock_id"]),
                "stock_name": str(r["stock_name"] or r["stock_id"]),
                "market": format_market(str(r["type"] or "")),
                "type": str(r["type"] or ""),
                "industry_category": str(r["industry_category"] or ""),
            }
            for r in rows
        ]

    def get_industry_categories(self) -> List[str]:
        """Return sorted list of distinct non-empty industry categories among supported common stocks."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT industry_category
                FROM stock_info
                WHERE is_supported = 1
                  AND industry_category IS NOT NULL
                  AND TRIM(industry_category) != ''
                ORDER BY industry_category ASC
                """
            )
            rows = cursor.fetchall()
        return [str(r["industry_category"]) for r in rows]

    def search_stocks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search supported common stocks matching query in stock_id or stock_name.

        Prioritizes:
        0. Exact stock_id match
        1. Exact stock_name match
        2. stock_id prefix match
        3. stock_name prefix match
        4. stock_id substring match
        5. stock_name substring match
        Tie-breaker: numerical/alphabetical stock_id.
        """
        q = query.strip()
        if not q:
            return []

        pattern = f"%{q}%"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT stock_id, stock_name, type, industry_category
                FROM stock_info
                WHERE is_supported = 1 AND (stock_id LIKE ? OR stock_name LIKE ?)
                """,
                (pattern, pattern),
            )
            rows = cursor.fetchall()

        candidates = [dict(r) for r in rows]

        def rank_key(item: Dict[str, Any]):
            sid = item["stock_id"]
            sname = item["stock_name"]
            if sid == q:
                return (0, 0, sid)
            if sname == q:
                return (1, 0, sid)
            if sid.startswith(q):
                return (2, 0, sid)
            if sname.startswith(q):
                return (3, 0, sid)
            if q in sid:
                return (4, sid.find(q), sid)
            return (5, sname.find(q), sid)

        candidates.sort(key=rank_key)
        top_candidates = candidates[:limit]

        return [
            {
                "stock_id": item["stock_id"],
                "stock_name": item["stock_name"],
                "name": item["stock_name"],
                "market": format_market(item.get("type", "")),
                "type": format_market(item.get("type", "")),
                "industry_category": item.get("industry_category", ""),
            }
            for item in top_candidates
        ]

    def is_unsupported_stock(self, query: str) -> bool:
        """Check whether query matches a known unsupported security (ETF, warrant, emerging, preferred)."""
        q = query.strip()
        if not q:
            return False

        # Pattern-based heuristic checks
        # Taiwan ETF / ETN start with 00, 01, 02
        if q.startswith(("00", "01", "02")):
            return True
        # Warrants: 6 alphanumeric / digits
        if len(q) == 6:
            return True
        # Preferred stocks: 4 digits + letter (e.g. 2881A)
        if len(q) == 5 and q[:4].isdigit() and q[4].isalpha():
            return True

        # Database check against unsupported entries in stock_info
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT stock_id FROM stock_info
                WHERE is_supported = 0 AND (stock_id = ? OR stock_name = ? OR stock_id LIKE ? OR stock_name LIKE ?)
                LIMIT 1
                """,
                (q, q, f"%{q}%", f"%{q}%"),
            )
            row = cursor.fetchone()
            return row is not None

    # --- Query Operations with Point-in-time (as_of) Support ---

    def get_market_index(self, index_id: str = "TAIEX", as_of_date: Optional[str] = None) -> pd.DataFrame:
        """Query market index daily records, optionally restricted to date <= as_of_date."""
        query = "SELECT * FROM market_index WHERE index_id = ?"
        params: List[Any] = [index_id]
        if as_of_date:
            query += " AND date <= ?"
            params.append(as_of_date)
        query += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

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

    # --- Nightly Plan Operations ---

    def save_nightly_plan(
        self,
        scan_date: str,
        items: List[Dict[str, Any]],
        plan_id: Optional[str] = None,
        status: str = "completed",
        total_candidates: int = 0,
        notes: Optional[str] = None,
    ) -> str:
        """Save a nightly plan and its items atomically."""
        if not plan_id:
            now_compact = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            plan_id = f"plan_{now_compact}"

        created_at = datetime.now(timezone.utc).isoformat()
        selected_count = len(items)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO nightly_plans
                (plan_id, scan_date, created_at, status, total_candidates, selected_count, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (plan_id, scan_date, created_at, status, total_candidates, selected_count, notes),
            )
            cursor.execute("DELETE FROM nightly_plan_items WHERE plan_id = ?", (plan_id,))

            for it in items:
                cursor.execute(
                    """
                    INSERT INTO nightly_plan_items
                    (plan_id, stock_id, stock_name, market, strategy, win_rate,
                     trade_count, entry_price, stop_loss, take_profit, holding_days,
                     risk_reward_ratio, close_price, volume, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        str(it.get("stock_id", "")),
                        str(it.get("stock_name", "")),
                        str(it.get("market", "")),
                        str(it.get("strategy", "")),
                        float(it.get("win_rate", 0.0)),
                        int(it.get("trade_count", 0)),
                        float(it.get("entry_price", 0.0)),
                        float(it.get("stop_loss", 0.0)),
                        float(it.get("take_profit", 0.0)),
                        int(it.get("holding_days", 5)),
                        float(it.get("risk_reward_ratio", 0.0)),
                        float(it.get("close_price", 0.0)),
                        float(it.get("volume", 0.0)),
                        str(it.get("reason", "")),
                    ),
                )
            conn.commit()
        return plan_id

    def get_nightly_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a nightly plan with its items by plan_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nightly_plans WHERE plan_id = ?", (plan_id,))
            plan_row = cursor.fetchone()
            if not plan_row:
                return None
            plan = dict(plan_row)

            cursor.execute(
                "SELECT * FROM nightly_plan_items WHERE plan_id = ? ORDER BY win_rate DESC, item_id ASC",
                (plan_id,),
            )
            plan["items"] = [dict(row) for row in cursor.fetchall()]
            return plan

    def get_latest_nightly_plan(self) -> Optional[Dict[str, Any]]:
        """Get the most recent nightly plan with its items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT plan_id FROM nightly_plans ORDER BY scan_date DESC, created_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_nightly_plan_by_id(row["plan_id"])

    def get_nightly_plan_by_date(self, scan_date: str) -> Optional[Dict[str, Any]]:
        """Get the latest nightly plan for a specific scan date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT plan_id FROM nightly_plans WHERE scan_date = ? ORDER BY created_at DESC LIMIT 1",
                (scan_date,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_nightly_plan_by_id(row["plan_id"])

    def list_nightly_plans(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List past nightly plans without items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM nightly_plans ORDER BY scan_date DESC, created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_nightly_plan(self, plan_id: str) -> bool:
        """Delete a plan and its items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM nightly_plan_items WHERE plan_id = ?", (plan_id,))
            cursor.execute("DELETE FROM nightly_plans WHERE plan_id = ?", (plan_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Watchlist Operations ---

    def add_watchlist_item(
        self,
        stock_id: str,
        stock_name: str,
        added_date: str,
        added_price: float,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Add a stock to watchlist. Raises sqlite3.IntegrityError if stock_id already exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO watchlist (stock_id, stock_name, added_date, added_price, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (stock_id.strip(), stock_name.strip(), added_date.strip(), float(added_price), notes.strip()),
            )
            conn.commit()
        item = self.get_watchlist_item(stock_id.strip())
        if item is None:
            raise RuntimeError(f"Failed to retrieve watchlist item after insert: {stock_id}")
        return item

    def get_watchlist(self, group_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all stocks in watchlist, optionally filtered by group_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if group_id is not None:
                cursor.execute(
                    """
                    SELECT w.*
                    FROM watchlist w
                    INNER JOIN watchlist_group_items gi ON w.stock_id = gi.stock_id
                    WHERE gi.group_id = ?
                    ORDER BY w.created_at DESC
                    """,
                    (group_id,),
                )
            else:
                cursor.execute("SELECT * FROM watchlist ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    list_watchlist = get_watchlist

    def get_watchlist_item(self, stock_id: str) -> Optional[Dict[str, Any]]:
        """Get a single watchlist item by stock_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watchlist WHERE stock_id = ?", (stock_id.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_watchlist_item(self, stock_id: str) -> bool:
        """Remove a stock from watchlist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE stock_id = ?", (stock_id.strip(),))
            conn.commit()
            return cursor.rowcount > 0

    remove_watchlist_item = delete_watchlist_item

    def is_in_watchlist(self, stock_id: str) -> bool:
        """Check if stock_id is in watchlist."""
        return self.get_watchlist_item(stock_id.strip()) is not None

    # --- Watchlist Groups Operations ---

    def create_watchlist_group(self, name: str) -> Dict[str, Any]:
        """Create a new watchlist group."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Group name cannot be empty")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist_groups (name) VALUES (?)",
                (clean_name,),
            )
            group_id = cursor.lastrowid
            conn.commit()
        group = self.get_watchlist_group(group_id)
        if group is None:
            raise RuntimeError(f"Failed to retrieve group after creation: {group_id}")
        return group

    def get_watchlist_groups(self) -> List[Dict[str, Any]]:
        """Get all watchlist groups ordered by id ASC."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watchlist_groups ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_watchlist_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Get a single watchlist group by id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watchlist_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_watchlist_group_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single watchlist group by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watchlist_groups WHERE name = ?", (name.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_watchlist_group(self, group_id: int, name: str) -> Optional[Dict[str, Any]]:
        """Update a watchlist group name."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Group name cannot be empty")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE watchlist_groups SET name = ? WHERE id = ?",
                (clean_name, group_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_watchlist_group(group_id)

    def delete_watchlist_group(self, group_id: int) -> bool:
        """Delete a watchlist group by id (cascades to watchlist_group_items)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist_groups WHERE id = ?", (group_id,))
            conn.commit()
            return cursor.rowcount > 0

    def add_stock_to_group(self, stock_id: str, group_id: int) -> bool:
        """Associate a stock with a group."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO watchlist_group_items (stock_id, group_id)
                VALUES (?, ?)
                """,
                (stock_id.strip(), group_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def remove_stock_from_group(self, stock_id: str, group_id: int) -> bool:
        """Remove a stock from a specific group."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM watchlist_group_items WHERE stock_id = ? AND group_id = ?",
                (stock_id.strip(), group_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_groups_for_stock(self, stock_id: str) -> List[Dict[str, Any]]:
        """Get all groups associated with a stock."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT g.id, g.name, g.created_at
                FROM watchlist_groups g
                INNER JOIN watchlist_group_items gi ON g.id = gi.group_id
                WHERE gi.stock_id = ?
                ORDER BY g.id ASC
                """,
                (stock_id.strip(),),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_stocks_in_group(self, group_id: int) -> List[str]:
        """Get all stock_ids associated with a group."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT stock_id FROM watchlist_group_items WHERE group_id = ? ORDER BY created_at DESC",
                (group_id,),
            )
            return [row["stock_id"] for row in cursor.fetchall()]

    def set_stock_groups(self, stock_id: str, group_ids: List[int]) -> List[int]:
        """Replace all group associations for a stock."""
        clean_sid = stock_id.strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist_group_items WHERE stock_id = ?", (clean_sid,))
            for gid in set(group_ids):
                cursor.execute(
                    "INSERT INTO watchlist_group_items (stock_id, group_id) VALUES (?, ?)",
                    (clean_sid, gid),
                )
            conn.commit()
        return list(set(group_ids))

    # --- AI Advice Cache Operations ---

    def get_ai_advice(self, stock_id: str, eval_date: str) -> Optional[Dict[str, Any]]:
        """Get cached AI advice for a stock on a specific evaluation date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT stock_id, eval_date, content, created_at FROM ai_advice_cache WHERE stock_id = ? AND eval_date = ?",
                (stock_id.strip(), eval_date.strip()),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_ai_advice(self, stock_id: str, eval_date: str, content: str) -> None:
        """Save or overwrite AI advice in cache."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ai_advice_cache (stock_id, eval_date, content, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(stock_id, eval_date) DO UPDATE SET
                    content = excluded.content,
                    created_at = CURRENT_TIMESTAMP
                """,
                (stock_id.strip(), eval_date.strip(), content),
            )
            conn.commit()


