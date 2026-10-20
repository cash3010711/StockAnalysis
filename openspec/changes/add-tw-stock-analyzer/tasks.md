# Tasks

## 1. 專案骨架與環境

- [ ] 1.1 建立 `backend/`（uv 專案：fastapi、uvicorn、pandas、numpy、httpx、python-dotenv、pytest），以及 `app/{api,data,analysis,backtest}`、`tests/` 目錄；驗證 `uv run pytest` 可執行（0 個測試、無錯誤）
- [ ] 1.2 建立 FastAPI 進入點與 `GET /api/health`，用 `.env` 載入 `FINMIND_TOKEN`，新增 `.env.example`，並把 `.env`、`data/cache.db` 加入 `.gitignore`；驗證 `uv run uvicorn app.main:app` 啟動後，`/api/health` 回傳 200
- [ ] 1.3 用 Vite 建立 `frontend/`（React + TypeScript），安裝 `lightweight-charts`，設定 `/api` proxy 到 `localhost:8000`；驗證 `npm run dev` 的頁面能顯示 `/api/health` 的結果
- [ ] 1.4 撰寫根目錄 `README.md`：申請 FinMind token 的步驟，以及 Windows 上啟動前後端的指令；驗證照著 README 可以從乾淨環境把兩者跑起來

## 2. 資料層：FinMind 用戶端與 SQLite 快取

- [ ] 2.1 實作 `data/finmind_client.py`：取得股票清單、日 K（還原權值）、三大法人、融資融券、月營收、季財報，並把 token 缺失、額度用盡轉成自訂例外；用實際 token 確認各資料集名稱與欄位，並錄製回應 fixture；驗證 mock HTTP 的單元測試涵蓋成功、`TOKEN_MISSING`、`QUOTA_EXCEEDED`
- [ ] 2.2 實作 `data/cache.py`：建立 SQLite schema（各資料表、主鍵 `(stock_id, date)`、`effective_date`、`fetch_log`）與 upsert；驗證測試確認重複寫入不產生重複列
- [ ] 2.3 實作 `data/publication.py` 推算生效日（優先用實際公布日；否則月營收用次月 10 日，季報用 5/15、8/14、11/14、3/31）；驗證測試涵蓋四季與跨年的 Q4
- [ ] 2.4 實作增量更新流程：依 `fetch_log` 只抓新資料；台北時間 14:30 前只抓到前一交易日；已是最新則不發請求；驗證測試用假的 client 計算請求次數，確認第二次分析不重抓歷史資料
- [ ] 2.5 實作額度用盡時改用快取並附警示、無快取時回傳錯誤，以及資料不足 5 年的警示；驗證測試涵蓋 `market-data` spec 的三個錯誤情境
- [ ] 2.6 實作 `as_of(stock_id, date)` 時點正確的資料視圖；驗證測試確認 9/20 取不到 9 月營收、10/11 取得到

## 3. 股票查詢（stock-lookup）

- [ ] 3.1 實作股票清單快取（超過 7 天自動更新），並排除 ETF、權證、興櫃、特別股；驗證測試確認 `0050` 被排除，對照表過期時會重新抓取
- [ ] 3.2 實作 `GET /api/stocks?q=`：支援代號或名稱部分比對，完全相符與開頭相符排前，最多 10 筆；驗證 API 測試涵蓋 `2330`、「鴻」、查無結果，以及 `0050` 回傳 `STOCK_NOT_SUPPORTED` 提示

## 4. 技術指標與三層條件（signal-analysis）

- [ ] 4.1 實作 `analysis/indicators.py`：MA、ATR(14)、MACD(12,26,9)、KD(9,3,3)、20 日最高價、20 日均量；驗證測試用手算的小型 fixture 比對數值（誤差 < 1e-6）
- [ ] 4.2 實作 `analysis/params.py` 集中預設門檻，以及 `analysis/layers.py` 的基本面、籌碼面每日判定序列（用 `merge_asof` 依 `effective_date` 展開），並附未通過原因字串；驗證測試涵蓋 spec 的通過與未通過情境
- [ ] 4.3 實作 `analysis/strategies.py` 的 4 個策略訊號序列（均線拉回 20MA、帶量突破 20 日新高、MACD 金叉、KD 低檔金叉）；驗證每個策略都有成立與不成立的 fixture 測試
- [ ] 4.4 實作 `analysis/exits.py`：用 ATR 計算停利、停損，並依台股升降單位四捨五入；驗證測試確認收盤 100、ATR 3 時得到 94／109，並涵蓋升降單位邊界（10、50、100、500、1000 元）
- [ ] 4.5 實作今日分析組裝：評估日（最近已收盤交易日）、每個策略的進場點位或觀望狀態、觸發條件價位（例如突破所需價位），以及各層原因；驗證測試涵蓋「只差技術面」與「基本面未通過」兩個 spec 情境

## 5. 回測引擎（strategy-backtest）

- [ ] 5.1 實作 `backtest/engine.py` 逐日狀態機：隔日開盤進場、不重疊持倉、進場時固定停利停損價；驗證測試確認 3/5 訊號在 3/6 開盤進場，持倉中的新訊號被忽略
- [ ] 5.2 實作出場判定：跳空低於停損以開盤價出場、同日觸及兩者判停損、持有 20 日到期依成本後報酬判輸贏；驗證每條規則都有獨立的 fixture 測試
- [ ] 5.3 實作交易成本（手續費 0.1425%×2、證交稅 0.3%）與 `backtest/stats.py`（筆數、勝率、平均報酬、期望值、平均持有天數、最大回檔、樣本不足旗標、「無交易」處理）；驗證測試確認 100→101 的報酬約 +0.41%，30 筆中 18 贏時勝率為 60.0%
- [ ] 5.4 串接三層條件與純技術面兩種進場遮罩，以及回測期間規則（5 年；不足 1 年不回測）；驗證測試確認歷史上籌碼面未通過的日子不進場，並確認兩組結果都會產生
- [ ] 5.5 撰寫偷看未來的防護測試：把評估日之後的資料改成極端值，確認歷史交易與統計完全不變；同時驗證相同輸入重跑兩次結果相同（可重現性）

## 6. 分析 API

- [ ] 6.1 實作 `GET /api/analysis/{stock_id}`：串接資料更新、今日分析、兩組回測，回傳評估日、警示、三層摘要、策略列表、交易明細、OHLCV；驗證 API 測試用錄製的 fixture 比對回應結構
- [ ] 6.2 統一錯誤格式 `{code, message, hint}`（`TOKEN_MISSING`、`QUOTA_EXCEEDED`、`STOCK_NOT_SUPPORTED`、`INSUFFICIENT_HISTORY`）；驗證 API 測試涵蓋每種錯誤碼的 HTTP 狀態與內容

## 7. 前端頁面（analysis-dashboard）

- [ ] 7.1 定義 API 回應的 TypeScript 型別與 fetch 封裝，並實作查詢框（debounce 250ms、最多 10 筆候選、查無結果提示）；驗證 Vitest 元件測試涵蓋選取候選後觸發分析
- [ ] 7.2 實作評估日標題、免責說明、三層摘要卡片（✓／✗、實際數值、未通過原因），以及載入、錯誤、警示訊息；驗證元件測試涵蓋 `TOKEN_MISSING` 顯示設定步驟
- [ ] 7.3 實作策略比較表（今日狀態、點位或觸發條件、兩組勝率與筆數、期望值、最大回檔、樣本不足標記、進場列醒目），並可點選切換目前策略；驗證元件測試涵蓋 1 進場 3 觀望的顯示
- [ ] 7.4 實作 K 線圖：K 棒、成交量、所選策略的交易標記（贏輸不同色），以及今日進場、停利、停損的 price lines；驗證手動在瀏覽器中切換策略時標記會更新

## 8. 整合驗證

- [ ] 8.1 用真實 FinMind token 端到端分析 `2330`、`2454`，以及一檔上櫃股票：確認首次分析在額度內完成、第二次分析數秒內回應，且畫面數值和 API 回應一致
- [ ] 8.2 抽查回測正確性：從 `2330` 某策略的交易明細挑 3 筆，對照原始日 K 手算進出場價與報酬，確認一致並把結果記錄在 `README.md`

## Workflow follow-up

- 實作與驗證完成後，執行 `/opsx-archive` 歸檔此變更，把 delta specs 併入 `openspec/specs/`。
