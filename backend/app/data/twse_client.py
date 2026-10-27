"""TWSE and TPEx daily quote client for batch fetching all-market daily quotes."""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Dict, List, Optional
import httpx

from app.data.stock_filter import is_supported_common_stock

TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TPEX_URL = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
TPEX_OPENAPI_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class DailyQuote:
    """Standardized daily quote item."""
    stock_id: str
    stock_name: str
    date: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    change: float
    change_pct: float
    volume: int  # in shares
    volume_lots: float  # in lots (張, volume / 1000)
    market: str  # "TWSE" or "TPEx"


def _clean_number(val: Any) -> Optional[float]:
    """Parse string with commas or special chars into float, returning None if invalid."""
    if val is None:
        return None
    s = str(val).replace(",", "").strip()
    if not s or s in ("--", "-", "N/A", "null"):
        return None
    # Strip HTML tags if present
    s = re.sub(r"<[^>]+>", "", s).strip()
    # Strip leading +
    if s.startswith("+"):
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


class TWSEClient:
    """Client for fetching and parsing daily market summaries from TWSE & TPEx."""

    def __init__(
        self,
        http_client: Optional[httpx.Client] = None,
        verify_ssl: bool = False,
        timeout: float = 30.0,
    ):
        self._external_client = http_client is not None
        self._client = http_client or httpx.Client(
            verify=verify_ssl,
            timeout=timeout,
            headers=DEFAULT_HEADERS,
        )

    def close(self):
        if not self._external_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def parse_twse_response(data: Dict[str, Any], date_str: str) -> List[DailyQuote]:
        """Parse TWSE MI_INDEX JSON response into a list of DailyQuote objects."""
        # Standardize date to YYYY-MM-DD
        clean_date = date_str.replace("/", "-")
        if len(clean_date) == 8 and clean_date.isdigit():
            clean_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}"

        quotes: List[DailyQuote] = []
        tables = data.get("tables", [])
        raw_rows = []

        # Find the table containing all quotes
        if tables:
            for t in tables:
                fields = t.get("fields", [])
                if any("收盤價" in f for f in fields) and any("證券代號" in f for f in fields):
                    raw_rows = t.get("data", [])
                    break
        elif "data" in data and "fields" in data:
            raw_rows = data.get("data", [])
        elif "data9" in data:  # Legacy TWSE JSON format
            raw_rows = data.get("data9", [])

        for row in raw_rows:
            if not isinstance(row, (list, tuple)) or len(row) < 9:
                continue
            stock_id = str(row[0]).strip()
            stock_name = str(row[1]).strip()

            # Filter only common stocks
            if not is_supported_common_stock(stock_id=stock_id, stock_name=stock_name, stock_type="twse"):
                continue

            vol_val = _clean_number(row[2])
            volume_shares = int(vol_val) if vol_val is not None else 0
            open_p = _clean_number(row[5])
            high_p = _clean_number(row[6])
            low_p = _clean_number(row[7])
            close_p = _clean_number(row[8])

            if close_p is None:
                continue
            if open_p is None:
                open_p = close_p
            if high_p is None:
                high_p = max(open_p, close_p)
            if low_p is None:
                low_p = min(open_p, close_p)

            # Change parsing: row[9] is sign, row[10] is diff
            sign_str = str(row[9]) if len(row) > 9 else ""
            diff_val = _clean_number(row[10]) if len(row) > 10 else 0.0
            diff = diff_val if diff_val is not None else 0.0
            if "-" in sign_str:
                diff = -abs(diff)
            elif "+" in sign_str:
                diff = abs(diff)

            prev_close = close_p - diff
            change_pct = round((diff / prev_close) * 100, 2) if prev_close > 0 else 0.0

            quotes.append(
                DailyQuote(
                    stock_id=stock_id,
                    stock_name=stock_name,
                    date=clean_date,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    change=round(diff, 2),
                    change_pct=change_pct,
                    volume=volume_shares,
                    volume_lots=round(volume_shares / 1000.0, 2),
                    market="TWSE",
                )
            )

        return quotes

    @staticmethod
    def parse_tpex_response(data: Any, date_str: str) -> List[DailyQuote]:
        """Parse TPEx stk_quote_result or openapi JSON into DailyQuote objects."""
        clean_date = date_str.replace("/", "-")
        if len(clean_date) == 8 and clean_date.isdigit():
            clean_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}"

        quotes: List[DailyQuote] = []

        # Case 1: OpenAPI format (list of dicts)
        if isinstance(data, list):
            for item in data:
                stock_id = str(item.get("SecuritiesCompanyCode", "")).strip()
                stock_name = str(item.get("CompanyName", "")).strip()
                if not is_supported_common_stock(stock_id=stock_id, stock_name=stock_name, stock_type="tpex"):
                    continue

                close_p = _clean_number(item.get("Close"))
                if close_p is None:
                    continue
                open_p = _clean_number(item.get("Open")) or close_p
                high_p = _clean_number(item.get("High")) or max(open_p, close_p)
                low_p = _clean_number(item.get("Low")) or min(open_p, close_p)
                diff = _clean_number(item.get("Change")) or 0.0
                vol_shares = int(_clean_number(item.get("TradingShares")) or 0)

                prev_close = close_p - diff
                change_pct = round((diff / prev_close) * 100, 2) if prev_close > 0 else 0.0

                quotes.append(
                    DailyQuote(
                        stock_id=stock_id,
                        stock_name=stock_name,
                        date=clean_date,
                        open=open_p,
                        high=high_p,
                        low=low_p,
                        close=close_p,
                        change=round(diff, 2),
                        change_pct=change_pct,
                        volume=vol_shares,
                        volume_lots=round(vol_shares / 1000.0, 2),
                        market="TPEx",
                    )
                )
            return quotes

        # Case 2: stk_quote_result.php (dict with aaData)
        if isinstance(data, dict):
            raw_rows = data.get("aaData", [])
            for row in raw_rows:
                if not isinstance(row, (list, tuple)) or len(row) < 8:
                    continue
                stock_id = str(row[0]).strip()
                stock_name = str(row[1]).strip()
                if not is_supported_common_stock(stock_id=stock_id, stock_name=stock_name, stock_type="tpex"):
                    continue

                close_p = _clean_number(row[2])
                if close_p is None:
                    continue
                diff = _clean_number(row[3]) or 0.0
                open_p = _clean_number(row[4]) or close_p
                high_p = _clean_number(row[5]) or max(open_p, close_p)
                low_p = _clean_number(row[6]) or min(open_p, close_p)
                vol_shares = int(_clean_number(row[7]) or 0)

                prev_close = close_p - diff
                change_pct = round((diff / prev_close) * 100, 2) if prev_close > 0 else 0.0

                quotes.append(
                    DailyQuote(
                        stock_id=stock_id,
                        stock_name=stock_name,
                        date=clean_date,
                        open=open_p,
                        high=high_p,
                        low=low_p,
                        close=close_p,
                        change=round(diff, 2),
                        change_pct=change_pct,
                        volume=vol_shares,
                        volume_lots=round(vol_shares / 1000.0, 2),
                        market="TPEx",
                    )
                )

        return quotes

    def fetch_twse_quotes(self, date_str: str) -> List[DailyQuote]:
        """Fetch TWSE daily quotes for a specific date (YYYY-MM-DD or YYYYMMDD)."""
        dt_param = date_str.replace("-", "").replace("/", "")
        params = {
            "date": dt_param,
            "type": "ALLBUT0999",
            "response": "json",
        }
        resp = self._client.get(TWSE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        return self.parse_twse_response(data, date_str)

    def fetch_tpex_quotes(self, date_str: str) -> List[DailyQuote]:
        """Fetch TPEx daily quotes for a specific date."""
        # Convert YYYY-MM-DD to ROC date YYY/MM/DD
        parts = date_str.replace("/", "-").split("-")
        if len(parts) == 3:
            roc_year = int(parts[0]) - 1911
            roc_date = f"{roc_year}/{parts[1]}/{parts[2]}"
        else:
            roc_date = date_str

        params = {
            "l": "zh-tw",
            "d": roc_date,
        }
        try:
            resp = self._client.get(TPEX_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            quotes = self.parse_tpex_response(data, date_str)
            if quotes:
                return quotes
        except Exception:
            pass

        # Fallback to TPEx openapi
        try:
            resp = self._client.get(TPEX_OPENAPI_URL)
            if resp.status_code == 200:
                data = resp.json()
                return self.parse_tpex_response(data, date_str)
        except Exception:
            pass

        return []

    def fetch_all_quotes(self, date_str: str) -> List[DailyQuote]:
        """Fetch both TWSE and TPEx quotes and return combined list."""
        twse_quotes = []
        tpex_quotes = []

        try:
            twse_quotes = self.fetch_twse_quotes(date_str)
        except Exception:
            pass

        try:
            tpex_quotes = self.fetch_tpex_quotes(date_str)
        except Exception:
            pass

        return twse_quotes + tpex_quotes

    @staticmethod
    def filter_candidates(
        quotes: List[DailyQuote],
        min_volume_lots: float = 1000.0,
        min_price: float = 10.0,
        top_n: int = 50,
        sort_by: str = "volume",
        require_bullish: bool = False,
    ) -> List[DailyQuote]:
        """Filter quotes for stage 1 candidate pool:

        1. Volume >= min_volume_lots (default 1000 lots)
        2. Close >= min_price (default 10 TWD)
        3. If require_bullish: Close >= Open or change > 0
        4. Sort by volume descending (or change_pct if sort_by='change_pct')
        """
        filtered = [
            q for q in quotes
            if q.volume_lots >= min_volume_lots
            and q.close >= min_price
            and (not require_bullish or (q.close >= q.open or q.change > 0))
        ]
        if sort_by == "change_pct":
            filtered.sort(key=lambda x: (x.change_pct, x.volume_lots), reverse=True)
        else:
            filtered.sort(key=lambda x: (x.volume_lots, x.change_pct), reverse=True)
        return filtered[:top_n]
