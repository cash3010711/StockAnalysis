import json
import os
from pathlib import Path
import httpx

FIXTURE_DIR = Path(__file__).resolve().parent / "finmind"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

client = httpx.Client(verify=False)

def fetch_and_save(dataset, params, filename):
    p = {"dataset": dataset, **params}
    r = client.get("https://api.finmindtrade.com/api/v4/data", params=p)
    data = r.json()
    filepath = FIXTURE_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {filename}, status={r.status_code}, items={len(data.get('data', []))}")

if __name__ == "__main__":
    fetch_and_save("TaiwanStockInfo", {}, "stock_info.json")
    fetch_and_save("TaiwanStockPrice", {"data_id": "2330", "start_date": "2024-01-02", "end_date": "2024-01-05"}, "daily_price.json")
    fetch_and_save("TaiwanStockInstitutionalInvestorsBuySell", {"data_id": "2330", "start_date": "2024-01-02", "end_date": "2024-01-03"}, "institutional.json")
    fetch_and_save("TaiwanStockMarginPurchaseShortSale", {"data_id": "2330", "start_date": "2024-01-02", "end_date": "2024-01-03"}, "margin_short.json")
    fetch_and_save("TaiwanStockMonthRevenue", {"data_id": "2330", "start_date": "2023-09-01", "end_date": "2024-01-01"}, "month_revenue.json")
    fetch_and_save("TaiwanStockFinancialStatements", {"data_id": "2330", "start_date": "2023-01-01", "end_date": "2023-12-31"}, "financial_statements.json")
    fetch_and_save("TaiwanStockBalanceSheet", {"data_id": "2330", "start_date": "2023-01-01", "end_date": "2023-12-31"}, "balance_sheet.json")
