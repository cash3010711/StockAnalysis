# Tasks: 自選股追蹤與進階圖表分析

## 1. 自選股後端資料庫模型與 API (Watchlist Backend & API)

- [ ] 1.1 於 `backend/app/data/cache.py` 建立 `watchlist` 資料表結構與 CRUD 函式（新增自選、刪除自選、取得清單），並在 `backend/tests/test_watchlist_cache.py` 撰寫測試驗證建立、查詢與防重複寫入；執行 `uv run --project backend pytest backend/tests/test_watchlist_cache.py`。
- [ ] 1.2 建立 `backend/app/api/watchlist.py` 路由（支援 `GET /api/watchlist`、`POST /api/watchlist`、`DELETE /api/watchlist/{stock_id}`），整合當前股票最新收盤價，並在 `backend/tests/test_watchlist_api.py` 驗證 API 格式與狀態代碼；執行 `uv run --project backend pytest backend/tests/test_watchlist_api.py`。

## 2. 季線與半年線指標計算與選股過濾 (60MA/120MA & Scanner Filter)

- [ ] 2.1 於 `backend/app/analysis/indicators.py` 與 `analysis.py` 擴充 `ma60` 與 `ma120` 計算與回傳欄位；在 `backend/app/analysis/scanner.py` 新增 `require_above_ma60` 篩選過濾；執行 `uv run --project backend pytest backend/tests/test_indicators.py backend/tests/test_scanner.py` 驗證數值與篩選正確性。
- [ ] 2.2 在 `frontend/src/types/api.ts` 與 `frontend/src/components/StockChart.tsx` 建立 60MA（森林綠）與 120MA（磚紅）LineSeries，預設為關閉狀態 `[ ]`，並在頂部工具列加入開關切換與 Legend 數值；執行 `cd frontend; npm test -- --run; cd ..` 驗證渲染。

## 3. 三大法人籌碼副圖與累積權益曲線 (Institutional Pane & Equity Curve)

- [ ] 3.1 擴充 `backend/app/api/analysis.py` 回傳近 30 日三大法人淨買賣超序列；在 `StockChart.tsx` 實作三大法人買賣超副圖與成交量副圖切換控制，確保游標懸停即時同步對齊；執行 `cd frontend; npm test -- --run; cd ..` 驗證切換互動。
- [ ] 3.2 擴充 `backend/app/analysis/backtest.py` 與 `assembler.py` 產出策略回測累積權益（`equity_curve`）與回撤序列；在 `frontend/src/components/StrategyTable.tsx` 實作點擊展開策略累積權益與最大回撤走勢圖卡片；執行 `cd frontend; npm test -- --run; cd ..` 驗證展開圖表。

## 4. 前端自選股管理面板與端對端整合 (Watchlist View & Integration)

- [ ] 4.1 建立 `frontend/src/components/WatchlistView.tsx` 自選股管理面板，於頂部導覽列新增「自選股追蹤」分頁，並在個股分析頂部加入 ⭐ 收藏/取消收藏按鈕與 API 串接；執行 `cd frontend; npm run build; npm test -- --run; cd ..` 驗證型別與畫面運作。
- [ ] 4.2 執行後端全套 pytest 與前端全套 vitest 回歸測試，確認個股深度分析、全市場選股、自選股追蹤三者分頁狀態保持、圖表切換流暢且無回歸錯誤。
