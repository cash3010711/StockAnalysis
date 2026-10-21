"""FinMind API client with custom error handling and dataset fetchers."""
from typing import Any, Dict, List, Optional
import httpx
import pandas as pd

from app.config import get_finmind_token, is_empty_token_allowed
from app.data.exceptions import (
    FinMindApiError,
    FinMindQuotaExceededError,
    FinMindTokenMissingError,
)
from app.data.publication import (
    get_monthly_revenue_effective_date,
    get_quarterly_financials_effective_date,
    quarter_from_date,
)

DEFAULT_BASE_URL = "https://api.finmindtrade.com/api/v4/data"


class FinMindClient:
    """Client for querying FinMind Taiwan stock market datasets."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: Optional[httpx.Client] = None,
        verify_ssl: bool = False,
        allow_empty_token: Optional[bool] = None,
    ):
        self.base_url = base_url
        self._external_client = http_client is not None
        self._client = http_client or httpx.Client(verify=verify_ssl, timeout=30.0)

        if token is not None:
            self.token = token
            self.allow_empty_token = (
                allow_empty_token if allow_empty_token is not None else False
            )
        else:
            self.token = get_finmind_token()
            self.allow_empty_token = (
                allow_empty_token if allow_empty_token is not None else is_empty_token_allowed()
            )

    def close(self):
        """Close underlying HTTP client if created internally."""
        if not self._external_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_token(self):
        """Ensure token exists, otherwise raise FinMindTokenMissingError."""
        if self.allow_empty_token:
            return
        if not self.token or not self.token.strip():
            raise FinMindTokenMissingError()

    def _request(
        self,
        dataset: str,
        params: Optional[Dict[str, Any]] = None,
        check_token: bool = True,
    ) -> List[Dict[str, Any]]:
        """Send request to FinMind API and parse response."""
        if check_token:
            self._ensure_token()

        req_params: Dict[str, Any] = {"dataset": dataset}
        if params:
            req_params.update(params)

        if self.token and self.token.strip():
            req_params["token"] = self.token

        try:
            resp = self._client.get(self.base_url, params=req_params)
        except httpx.HTTPError as e:
            raise FinMindApiError(f"HTTP request failed: {e}") from e

        # Handle HTTP 402 Payment Required
        if resp.status_code == 402:
            raise FinMindQuotaExceededError()

        try:
            data = resp.json()
        except Exception as e:
            raise FinMindApiError(
                f"Invalid JSON response from FinMind: {resp.text[:200]}",
                status_code=resp.status_code,
            ) from e

        msg = str(data.get("msg", ""))
        status = data.get("status")

        # Check quota exceeded patterns
        if status == 402 or "upper limit" in msg.lower() or "reach the upper limit" in msg:
            raise FinMindQuotaExceededError()

        # Check illegal or missing token patterns
        if "token is illegal" in msg.lower() or "token missing" in msg.lower():
            raise FinMindTokenMissingError(message=f"FinMind token 無效: {msg}")

        # If HTTP code was not 200 or status not 200
        if resp.status_code != 200 or status != 200:
            raise FinMindApiError(
                f"FinMind API error ({status or resp.status_code}): {msg}",
                status_code=status or resp.status_code,
            )

        return data.get("data", [])

    def get_stock_info(self) -> pd.DataFrame:
        """Fetch Taiwan stock list (TaiwanStockInfo)."""
        # Token is not strictly required for TaiwanStockInfo in FinMind, but we send if available
        records = self._request("TaiwanStockInfo", check_token=False)
        return pd.DataFrame(records)

    def get_daily_k(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV K-bars.

        If adjusted=True, tries TaiwanStockPriceAdj first. If free tier rejects it,
        falls back to TaiwanStockPrice.
        """
        params: Dict[str, Any] = {"data_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        dataset = "TaiwanStockPriceAdj" if adjusted else "TaiwanStockPrice"
        try:
            records = self._request(dataset, params)
        except FinMindApiError as e:
            # Fallback for free user accounts where TaiwanStockPriceAdj is restricted
            if adjusted and "level is free" in str(e).lower():
                records = self._request("TaiwanStockPrice", params)
            else:
                raise

        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "stock_id", "date", "open", "high", "low", "close",
                    "volume", "money", "spread", "turnover",
                ]
            )

        # Standardize column names
        rename_map = {
            "max": "high",
            "min": "low",
            "Trading_Volume": "volume",
            "Trading_money": "money",
            "Trading_turnover": "turnover",
        }
        df = df.rename(columns=rename_map)

        # Ensure correct column types
        numeric_cols = ["open", "high", "low", "close", "volume", "money", "spread", "turnover"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_institutional_investors(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch institutional investors buy/sell (TaiwanStockInstitutionalInvestorsBuySell)."""
        params: Dict[str, Any] = {"data_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        records = self._request("TaiwanStockInstitutionalInvestorsBuySell", params)
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(
                columns=["date", "stock_id", "name", "buy", "sell"]
            )

        for col in ["buy", "sell"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df

    def get_margin_short(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch margin purchase and short sale data (TaiwanStockMarginPurchaseShortSale)."""
        params: Dict[str, Any] = {"data_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        records = self._request("TaiwanStockMarginPurchaseShortSale", params)
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "stock_id", "date",
                    "margin_purchase_buy", "margin_purchase_sell", "margin_purchase_balance",
                    "short_sale_buy", "short_sale_sell", "short_sale_balance",
                ]
            )

        # Map to standard names
        rename_map = {
            "MarginPurchaseBuy": "margin_purchase_buy",
            "MarginPurchaseSell": "margin_purchase_sell",
            "MarginPurchaseTodayBalance": "margin_purchase_balance",
            "ShortSaleBuy": "short_sale_buy",
            "ShortSaleSell": "short_sale_sell",
            "ShortSaleTodayBalance": "short_sale_balance",
        }
        df = df.rename(columns=rename_map)

        for col in rename_map.values():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df

    def get_monthly_revenue(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch monthly revenue (TaiwanStockMonthRevenue)."""
        params: Dict[str, Any] = {"data_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        records = self._request("TaiwanStockMonthRevenue", params)
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "stock_id", "date", "revenue_year", "revenue_month",
                    "revenue", "actual_publication_date", "effective_date",
                ]
            )

        if "revenue" in df.columns:
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
        if "revenue_year" in df.columns:
            df["revenue_year"] = pd.to_numeric(df["revenue_year"], errors="coerce").astype(int)
        if "revenue_month" in df.columns:
            df["revenue_month"] = pd.to_numeric(df["revenue_month"], errors="coerce").astype(int)

        actual_dates = df["create_time"] if "create_time" in df.columns else [None] * len(df)
        df["actual_publication_date"] = actual_dates

        # Calculate effective_date
        effective_dates = []
        for _, row in df.iterrows():
            eff = get_monthly_revenue_effective_date(
                year=int(row["revenue_year"]),
                month=int(row["revenue_month"]),
                actual_date=row.get("actual_publication_date"),
            )
            effective_dates.append(eff)
        df["effective_date"] = effective_dates

        return df

    def get_financial_statements(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch income statement financial data (TaiwanStockFinancialStatements)."""
        params: Dict[str, Any] = {"data_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        records = self._request("TaiwanStockFinancialStatements", params)
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(columns=["date", "stock_id", "type", "value", "origin_name"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df

    def get_balance_sheet(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch balance sheet financial data (TaiwanStockBalanceSheet)."""
        params: Dict[str, Any] = {"data_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        records = self._request("TaiwanStockBalanceSheet", params)
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(columns=["date", "stock_id", "type", "value", "origin_name"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df

    def get_quarterly_financials(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch and combine quarterly EPS and Debt Ratio into a single dataset.

        Returns DataFrame with:
        stock_id, date, year, quarter, eps, debt_ratio, effective_date
        """
        fs_df = self.get_financial_statements(stock_id, start_date, end_date)
        bs_df = self.get_balance_sheet(stock_id, start_date, end_date)

        eps_map: Dict[str, float] = {}
        if not fs_df.empty and "type" in fs_df.columns:
            eps_rows = fs_df[fs_df["type"] == "EPS"]
            for _, r in eps_rows.iterrows():
                eps_map[str(r["date"])] = float(r["value"])

        debt_map: Dict[str, float] = {}
        if not bs_df.empty and "type" in bs_df.columns:
            # Check for direct Liabilities_per first
            debt_per_rows = bs_df[bs_df["type"] == "Liabilities_per"]
            for _, r in debt_per_rows.iterrows():
                debt_map[str(r["date"])] = float(r["value"])

            # If any date missing Liabilities_per, check Liabilities / TotalAssets * 100
            for d in bs_df["date"].unique():
                d_str = str(d)
                if d_str not in debt_map:
                    sub = bs_df[bs_df["date"] == d]
                    liab = sub[sub["type"] == "Liabilities"]["value"]
                    assets = sub[sub["type"] == "TotalAssets"]["value"]
                    if not liab.empty and not assets.empty and assets.values[0] != 0:
                        debt_map[d_str] = float((liab.values[0] / assets.values[0]) * 100)

        all_dates = sorted(list(set(eps_map.keys()) | set(debt_map.keys())))
        if not all_dates:
            return pd.DataFrame(
                columns=[
                    "stock_id", "date", "year", "quarter",
                    "eps", "debt_ratio", "effective_date",
                ]
            )

        rows = []
        for d in all_dates:
            year, quarter = quarter_from_date(d)
            eff_date = get_quarterly_financials_effective_date(year, quarter)
            rows.append({
                "stock_id": stock_id,
                "date": d,
                "year": year,
                "quarter": quarter,
                "eps": eps_map.get(d, 0.0),
                "debt_ratio": debt_map.get(d, 0.0),
                "effective_date": eff_date,
            })

        return pd.DataFrame(rows)
