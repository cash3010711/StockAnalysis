"""Data service coordinating incremental sync, cache, and point-in-time data views."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional
import pandas as pd

from app.data.cache import CacheRepository
from app.data.exceptions import (
    FinMindError,
    FinMindQuotaExceededError,
    FinMindTokenMissingError,
)
from app.data.finmind_client import FinMindClient

TAIPEI_TZ = timezone(timedelta(hours=8))
MARKET_CLOSE_TIME = time(14, 30)


@dataclass
class SyncResult:
    """Result of an incremental sync operation."""
    stock_id: str
    target_date: str
    latest_k_date: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    requests_made: int = 0
    quota_exceeded: bool = False


class DataService:
    """Coordinates fetching from FinMind, updating SQLite cache, and point-in-time views."""

    def __init__(
        self,
        client: Optional[FinMindClient] = None,
        repo: Optional[CacheRepository] = None,
    ):
        self.client = client or FinMindClient()
        self.repo = repo or CacheRepository()

    @staticmethod
    def get_target_trade_date(current_dt: Optional[datetime] = None) -> date:
        """Calculate target trade date based on Taipei time and 14:30 cutoff.

        Before 14:30 on trade day: target is previous calendar day.
        At or after 14:30: target is today.
        """
        if current_dt is None:
            current_dt = datetime.now(TAIPEI_TZ)
        elif current_dt.tzinfo is None:
            current_dt = current_dt.replace(tzinfo=TAIPEI_TZ)
        else:
            current_dt = current_dt.astimezone(TAIPEI_TZ)

        local_date = current_dt.date()
        local_time = current_dt.time()

        if local_time < MARKET_CLOSE_TIME:
            # Before 14:30, fetch up to yesterday
            return local_date - timedelta(days=1)
        else:
            # After 14:30, fetch up to today
            return local_date

    @staticmethod
    def get_five_years_start_date(target: date) -> date:
        """Compute start date 5 years prior to target date."""
        try:
            return target.replace(year=target.year - 5) + timedelta(days=1)
        except ValueError:
            # Leap year Feb 29 fallback
            return target.replace(year=target.year - 5, day=28) + timedelta(days=1)

    def sync_stock(
        self,
        stock_id: str,
        current_dt: Optional[datetime] = None,
    ) -> SyncResult:
        """Incrementally sync all 5 datasets for stock_id up to target date.

        Handles:
        - Skipping if already up to date (0 requests)
        - Token missing error
        - Quota exceeded with cache -> warning
        - Quota exceeded without cache -> error
        - Insufficient history (< 5 years) -> warning
        """
        target_date = self.get_target_trade_date(current_dt)
        target_str = target_date.isoformat()
        five_years_start = self.get_five_years_start_date(target_date).isoformat()

        result = SyncResult(stock_id=stock_id, target_date=target_str)

        # Dataset definitions and sync handlers
        datasets = [
            ("daily_k", self._sync_daily_k),
            ("institutional_investors", self._sync_institutional),
            ("margin_short", self._sync_margin_short),
            ("monthly_revenue", self._sync_monthly_revenue),
            ("quarterly_financials", self._sync_quarterly_financials),
        ]

        quota_hit = False

        for ds_name, fetch_and_save in datasets:
            last_fetched = self.repo.get_fetch_log(stock_id, ds_name)
            if last_fetched and last_fetched >= target_str:
                # Already fetched up to target_str, skip
                continue

            # Determine start date
            if last_fetched:
                start_d = date.fromisoformat(last_fetched) + timedelta(days=1)
                start_str = start_d.isoformat()
            else:
                start_str = five_years_start

            if start_str > target_str:
                self.repo.update_fetch_log(stock_id, ds_name, target_str)
                continue

            try:
                fetch_and_save(stock_id, start_str, target_str)
                result.requests_made += 1
                self.repo.update_fetch_log(stock_id, ds_name, target_str)
            except FinMindQuotaExceededError:
                quota_hit = True
                result.quota_exceeded = True
                break
            except FinMindTokenMissingError:
                raise
            except Exception as e:
                # Other API errors
                raise

        # Check existing cached K-bars
        existing_k = self.repo.get_daily_k(stock_id)

        if quota_hit:
            if existing_k.empty:
                # Quota exceeded and no cache at all -> raise error
                raise FinMindQuotaExceededError(
                    message="API 額度已用盡，請稍後再試",
                    hint="FinMind 免費方案每小時請求次數已達上限，且本機無快取資料，請稍後再試",
                )
            else:
                # Quota exceeded but cache exists -> add warning
                latest_d = existing_k["date"].max()
                result.warnings.append(f"資料截至 {latest_d}，API 額度已用盡")

        if not existing_k.empty:
            result.latest_k_date = existing_k["date"].max()
            first_d = date.fromisoformat(existing_k["date"].min())
            last_d = date.fromisoformat(existing_k["date"].max())
            years = (last_d - first_d).days / 365.25
            if years < 4.8:
                years_int = int(round(years)) if abs(years - round(years)) < 0.25 else round(years, 1)
                warn = f"歷史資料僅 {years_int} 年"
                if warn not in result.warnings:
                    result.warnings.append(warn)

        return result

    def _sync_daily_k(self, stock_id: str, start_date: str, end_date: str):
        df = self.client.get_daily_k(stock_id, start_date=start_date, end_date=end_date)
        if not df.empty:
            self.repo.upsert_daily_k(stock_id, df)

    def _sync_institutional(self, stock_id: str, start_date: str, end_date: str):
        df = self.client.get_institutional_investors(stock_id, start_date=start_date, end_date=end_date)
        if not df.empty:
            self.repo.upsert_institutional_investors(stock_id, df)

    def _sync_margin_short(self, stock_id: str, start_date: str, end_date: str):
        df = self.client.get_margin_short(stock_id, start_date=start_date, end_date=end_date)
        if not df.empty:
            self.repo.upsert_margin_short(stock_id, df)

    def _sync_monthly_revenue(self, stock_id: str, start_date: str, end_date: str):
        df = self.client.get_monthly_revenue(stock_id, start_date=start_date, end_date=end_date)
        if not df.empty:
            self.repo.upsert_monthly_revenue(stock_id, df)

    def _sync_quarterly_financials(self, stock_id: str, start_date: str, end_date: str):
        df = self.client.get_quarterly_financials(stock_id, start_date=start_date, end_date=end_date)
        if not df.empty:
            self.repo.upsert_quarterly_financials(stock_id, df)

    def as_of(self, stock_id: str, as_of_date: str) -> Dict[str, pd.DataFrame]:
        """Return point-in-time view as of the specified date."""
        return self.repo.as_of(stock_id, as_of_date)
