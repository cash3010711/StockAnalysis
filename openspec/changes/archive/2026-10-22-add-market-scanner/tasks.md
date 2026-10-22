# Tasks

## 1. 後端快取與股票池查詢擴充

- [x] 1.1 在 `backend/app/data/cache.py` 的 `CacheRepository` 新增 `get_stock_metadata`、`get_cached_stock_ids`、`get_supported_stocks` 與 `get_industry_categories` 方法，並執行 `uv run --project backend pytest backend/tests/test_cache.py` 確認既有快取測試通過
- [x] 1.2 在 `backend/app/analysis/scanner.py` 建立 `TAIWAN_50_STOCKS` 代表股清單、`ScanFilterConfig` 與 `resolve_scan_pool` 股票池解析邏輯（支援 `cached`、`tw50`、`industry`、`all`、`twse`、`tpex`），並以單元測試驗證各股票池與產業過濾結果正確

## 2. 後端兩階段選股掃描引擎與串流 API

- [x] 2.1 在 `backend/app/analysis/scanner.py` 實作 `scan_single_stock`（含向量化技術訊號初篩、Point-in-Time 三層檢驗、進出場點位計算與觸發策略歷史回測統計）及 `iter_scan_events`（含 FinMind API 額度上限熔斷降級機制）
- [x] 2.2 在 `backend/app/api/scanner.py` 新增 `GET /api/scanner/options`、`POST /api/scanner/run` 與 `POST /api/scanner/stream`（NDJSON 串流）端點，並於 `backend/app/main.py` 註冊 router
- [x] 2.3 新增 `backend/tests/test_scanner.py` 測試選項端點、三層與自訂條件過濾、NDJSON 串流事件及 API 額度上限自動降級行為，執行 `uv run --project backend pytest` 驗證全數通過

## 3. 前端選股掃描介面與雙分頁整合

- [x] 3.1 在 `frontend/src/types/api.ts` 與 `frontend/src/api/client.ts` 新增選股掃描型別定義及 `fetchScannerOptions`、`runMarketScan`、`streamMarketScan`（支援 `ReadableStream` 逐行解析與 `AbortSignal` 中止）函式
- [x] 3.2 建立 `frontend/src/components/MarketScanner.tsx`，實作股票池範圍選擇、產業過濾、快取／自動同步切換、基本面／籌碼面／5 大技術策略勾選、即時進度條與中止按鈕，以及支援多欄位排序的符合條件股票表格
- [x] 3.3 更新 `frontend/src/App.tsx` 新增頂部「個股深度分析／全市場選股掃描」雙分頁切換（保持 `MarketScanner` 掛載狀態以保留結果），支援從掃描列表點擊股票直接載入個股 K 線與深度分析
- [x] 3.4 新增 `frontend/src/components/MarketScanner.test.tsx` 整合測試，並執行 `npm test -- --run` 與 `npm run build` 驗證前端測試與 TypeScript 編譯全數通過
