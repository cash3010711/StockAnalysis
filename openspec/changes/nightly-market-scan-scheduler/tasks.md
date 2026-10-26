# Tasks: 兩階段全市場掃描與夜間自動備戰排程

## 1. 資料源與資料庫模型擴充 (Data Source & Database Model)

- [x] 1.1 建立 TWSE / TPEx 公開盤後日行情下載器 `backend/app/data/twse_client.py`，支援批次抓取全市場收盤價量，並新增單元測試 `backend/tests/test_twse_client.py` 驗證數據解析正確性。
- [x] 1.2 在 SQLite 快取庫新增 `nightly_plans` 與 `nightly_plan_items` 資料表與對應 CRUD 函式於 `backend/app/data/cache.py`，並撰寫單元測試 `backend/tests/test_nightly_cache.py` 驗證寫入與查詢功能。

## 2. 兩階段快篩與點位流水線 (Two-Stage Pipeline & Exits)

- [x] 2.1 擴充 `backend/app/analysis/scanner.py` 中的篩選流水線，實作兩階段掃描流程（第一階段以 TWSE 總表過濾出成交量 >= 1000 張且強勢標的，第二階段僅針對候選標的調用 FinMind 增量同步與三層驗證）。
- [x] 2.2 整合 `backend/app/analysis/exits.py`，為通過三層檢驗之標的計算隔日預計進場價、停損價、停利目標價與持有天數，並於 `backend/tests/test_two_stage_scan.py` 驗證運算結果與 API 請求數。

## 3. 夜間定時排程服務與 API (Nightly Scheduler & API Endpoints)

- [x] 3.1 於 `backend/pyproject.toml` 新增 `apscheduler` 依賴，建立定時背景工作模組 `backend/app/data/scheduler.py`，設定於台股交易日 18:30 自動執行兩階段掃描並存入資料庫，並掛載於 `backend/app/main.py` 之 lifespan 生命週期。
- [x] 3.2 於 `backend/app/api/scanner.py` 新增 `/api/scanner/nightly-plan` 與 `/api/scanner/nightly-plan/trigger` 端點，支援前端查詢最近一次作戰清單及手動補跑排程，並於 `backend/tests/test_scheduler_api.py` 驗證端點回應。

## 4. 前端隔日作戰清單面板 (Frontend Nightly Plan UI)

- [x] 4.1 在前端新增 `frontend/src/api/nightlyPlan.ts` 串接後端作戰清單 API 與手動補跑排程端點，定義型別介面。
- [x] 4.2 在選股掃描介面中新增「隔日交易備戰清單」卡片，直觀展示推薦股票、觸發策略、歷史回測勝率、建議進場價、停損價與停利價，並透過 `npm run build` 與 `npm test` 驗證畫面運作。
