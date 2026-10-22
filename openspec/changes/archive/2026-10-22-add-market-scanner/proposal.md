# Proposal

## Why

目前系統僅支援單一股票查詢與分析，使用者必須逐一輸入代號才能確認哪些標符合三層檢驗與今日技術進場訊號。新增「全市場選股掃描」功能可主動從指定股票池篩出符合波段條件的股票並列出關鍵點位與歷史回測勝率，大幅提升每日盤後選股效率。

## What Changes

- 新增後端選股掃描服務與 API（`GET /api/scanner/options`、`POST /api/scanner/run`、`POST /api/scanner/stream`），支援即時串流（NDJSON）回報掃描進度與符合條件之股票。
- 支援多層股票池選擇（本機已快取股票、熱門權值／台灣 50 代表股、全市場上市櫃普通股、僅上市、僅上櫃）與依產業類別過濾。
- 支援切換「僅掃描本機快取（極速、零 API 消耗）」與「自動向 FinMind 同步最新資料（遇 API 額度上限時自動降級使用本機快取）」。
- 支援彈性篩選條件組合：預設為「基本面合格＋籌碼面合格＋今日任一技術策略觸發進場訊號」，並允許使用者自訂開關基本面、籌碼面及勾選特定技術策略。
- 新增前端「全市場選股掃描」分頁與結果列表，顯示代號／名稱、收盤價、觸發策略標籤、建議進場／停損／停利價、基本面與籌碼面指標摘要、觸發策略之歷史回測勝率與平均報酬率，支援欄位排序與點擊跳轉至個股深度分析。

## Out of Scope

- 盤中即時逐筆報價（Tick）推播與自動下單功能。
- 跨市場（美股、加密貨幣）或非普通股（ETF、權證、興櫃、特別股）之選股掃描。
- 自訂技術指標公式編輯器或雲端排程推播通知（如 Line / Email 通知）。

## Capabilities

### New Capabilities
- `market-scanner`: 提供股票池範圍選擇、產業別過濾、快取／同步模式切換、三層檢驗與 5 大技術策略彈性組合篩選、即時進度串流與中止、以及可排序的符合條件股票列表。

### Modified Capabilities
- `analysis-dashboard`: 頂部導覽列新增「個股深度分析／全市場選股掃描」雙分頁切換，點擊掃描結果中的股票可直接載入該股完整 K 線與深度分析，且切回掃描分頁時保留掃描結果狀態。

## Impact

- 後端：`backend/app/data/cache.py`、`backend/app/analysis/scanner.py`、`backend/app/api/scanner.py`、`backend/app/main.py` 及單元測試 `backend/tests/test_scanner.py`。
- 前端：`frontend/src/types/api.ts`、`frontend/src/api/client.ts`、`frontend/src/components/MarketScanner.tsx`、`frontend/src/App.tsx` 及整合測試 `frontend/src/components/MarketScanner.test.tsx`。
