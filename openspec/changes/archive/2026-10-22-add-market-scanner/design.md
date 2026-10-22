# Design

## Context

目前系統已具備針對單一普通股之 FinMind 增量同步、SQLite 點位快取（`CacheRepository`）、Point-in-Time 三層檢驗（`assemble_today_analysis`）與 5 年歷史回測（`run_all_backtests`）。要擴充為全市場選股掃描（見 `proposal.md`），必須克服兩大技術挑戰：
1. **FinMind 免費 API 額度限制**：免費方案每小時僅約 600 次請求，而單檔完整同步需呼叫 5 個資料集，不可能在單次掃描中對全市場 1,800+ 檔無快取股票全部發起即時請求。
2. **多檔評估與回測的計算效能及回應體驗**：若對每檔股票皆完整執行 `merge_asof` 基本面／籌碼面對齊與 5 大策略 5 年回測，千檔掃描將造成前端長時間等待。

## Goals / Non-Goals

**Goals:**
- 提供分層股票池（本機已快取、台灣 50 代表股、全市場上市櫃、特定產業）與「僅掃快取／自動同步」雙模式，兼顧極速掃描與資料更新需求。
- 透過「技術指標向量化初篩（Fast Pre-check）」大幅降低不必要的基本面／籌碼面對齊與歷史回測運算成本。
- 採用 HTTP NDJSON 串流（`application/x-ndjson`）即時推送進度與符合標的，並支援前端 `AbortController` 隨時中止。
- 當開啟自動同步且遭遇 FinMind API 額度上限時，自動在同一次掃描工作階段中切換為本機快取降級模式，保留既有結果不中斷。

**Non-Goals:**
- 不引入額外的背景佇列中介軟體（如 Celery / Redis），維持單一本機 FastAPI + SQLite 輕量架構。
- 不另外爬取非 FinMind 之第三方網頁作為主要財報來源。

## Decisions

### 1. 兩階段快速篩選管線（Two-Stage Fast Filtering Pipeline）
- **決策**：在 `scan_single_stock` 中，先讀取該股 `daily_k` 並執行純向量化的 `compute_all_indicators` 與 `evaluate_all_strategies`，檢查最後一個交易日（`iloc[-1]`）是否有任何一個使用者勾選的技術策略觸發訊號。若無任何技術策略觸發，立即短路返回 `None`；僅在最後一日有技術訊號觸發時，才載入 Point-in-Time 財報／籌碼資料執行 `assemble_today_analysis`，並在通過基本面／籌碼面篩選後，僅針對當日有觸發的策略執行 `run_all_backtests(..., strategy_names=triggered_names)`。
- **理由**：每日全市場僅約 5%～15% 股票會觸發特定技術進場訊號。先以毫秒級的向量化技術訊號過濾，可省去 85% 以上標的中較耗時的 `iterrows()` 財報檢驗與歷史逐筆回測，使本機快取掃描速度提升 10 倍以上，且篩選結果與完整執行完全一致。
- **替代方案**：對每檔股票無條件先跑完 `assemble_today_analysis` 與全部 5 個策略的 `run_all_backtests` 後再過濾——在大股票池下會造成不必要的 CPU 計算延遲。

### 2. 使用 NDJSON 串流（`POST /api/scanner/stream`）回報進度與結果
- **決策**：後端以 FastAPI `StreamingResponse` 輸出 `application/x-ndjson`，依序發出 `start`、`match`、`progress`、`done` 四種 JSON 事件；前端使用原生 `fetch` 搭配 `ReadableStream.getReader()` 逐行解析，並透過 `AbortController` 支援手動中止。同時提供同步版 `POST /api/scanner/run` 供批次呼叫與整合測試使用。
- **理由**：相較於傳統 `EventSource`（SSE）僅支援 `GET` 且參數受限於 Query String，NDJSON over `POST` 可直接傳遞結構化篩選條件（`ScanRequestModel`），且原生支援 `AbortSignal` 中止連線。
- **替代方案**：
  - 單次同步 HTTP Request 等全部掃描完才回傳——掃描數十至數百檔時畫面無進度回饋且無法中途保留部分結果。
  - WebSocket——對於單向掃描串流而言狀態管理過度複雜。

### 3. 股票池分層與 API 額度熔斷降級（Quota Circuit Breaker）
- **決策**：
  - 在 `scanner.py` 內建 `TAIWAN_50_STOCKS`（50 檔台灣代表性權值普通股含預設名稱與產業），並在 `CacheRepository` 新增 `get_cached_stock_ids()`、`get_supported_stocks()` 與 `get_industry_categories()`。
  - 在單次掃描迴圈中維護 `quota_exceeded_session` 旗標：當 `sync_latest=True` 且某檔股票同步拋出 `FinMindQuotaExceededError` 時，立即將旗標設為 `True`，後續股票不再呼叫 FinMind API，自動改用本機 SQLite 快取繼續評估，並在回應附上警示訊息。
- **理由**：避免在觸發 600 次/小時上限後對剩餘數百檔股票重複發出必定失敗的 HTTP 請求，同時確保使用者仍能取得本機已快取股票的掃描結果。

### 4. 前端雙分頁狀態保持（Keep-Alive Scanner View）
- **決策**：在 `App.tsx` 頂部提供「個股深度分析」與「全市場選股掃描」切換分頁。一旦使用者開啟過「全市場選股掃描」，將 `MarketScanner` 元件保持掛載並以 CSS `display: block / none` 切換顯示。
- **理由**：當使用者從掃描結果點擊某檔股票進入「個股深度分析」查看 K 線圖後，再切回「全市場選股掃描」時，原有的掃描結果列表、排序狀態與篩選條件可完整保留，無須重新掃描。

## Risks / Trade-offs

- **[Risk] 全市場首次掃描時本機尚無快取資料** → **Mitigation**：於 `GET /api/scanner/options` 回傳 `cached_count`，若本機快取為 0 檔，前端預設引導選擇「熱門權值／台灣 50」並開啟「自動同步最新資料」，或透過產業分類分批同步建立快取。
- **[Risk] 使用者放寬基本面或籌碼面時三層回測交易筆數可能為 0** → **Mitigation**：在計算掃描列表的 `best_win_rate_pct` 與 `best_avg_return_pct` 時，若使用者取消勾選基本面或籌碼面（或三層回測無交易樣本），自動對應採用 `tech_only_stats`（純技術面歷史回測統計），確保列表排序與顯示數值符合當前篩選語意。
