# Tasks

## 1. 選股產業過濾簡化與兩階段快篩產業補齊

- [x] 1.1 在 `backend/app/analysis/params.py` 定義 `TECH_INDUSTRIES`（電子八大類），於 `backend/app/analysis/scanner.py` 新增產業別映射與科技/非科技過濾邏輯，並在兩階段初篩後加入 `_enrich_stock_metadata` 產業分類補齊；編寫並執行單元測試 `pytest tests/test_scanner_industry_filter.py` 驗證通過
- [x] 1.2 更新前端 `frontend/src/components/MarketScanner.tsx` 產業下拉選單為「全部產業」、「科技股（電子八大類）」、「非科技股」，並更新前端單元測試 `npm --prefix frontend test -- -t "industry"` 驗證篩選參數傳遞正確

## 2. 選股表格與夜間作戰清單一鍵加自選

- [x] 2.1 在 `frontend/src/components/MarketScanner.tsx` 傳入自選股清單與加/退自選回呼函式，於即時掃描結果表格與夜間作戰清單每列最左側新增 ⭐ 收藏按鈕，以高亮/空心星號反映公用池狀態；編寫前端測試驗證點擊切換收藏行爲
- [x] 2.2 在 `frontend/src/App.tsx` 整合選股與自選股狀態同步，手動或測試驗證選股清單點擊收藏時自選股公用池與頂部計數即時連動

## 3. 自選股多群組資料模型與後端 CRUD API

- [x] 3.1 在 `backend/app/data/cache.py` 建立 `watchlist_groups` 與 `watchlist_group_items` SQLite 表結構、索引與外鍵級聯刪除，並實作群組 CRUD 及股票群組關聯操作方法；編寫單元測試 `pytest tests/test_watchlist_groups_cache.py` 驗證通過
- [x] 3.2 在 `backend/app/api/watchlist.py` 實作群組端點（`GET /api/watchlist/groups`、`POST /api/watchlist/groups`、`DELETE /api/watchlist/groups/{id}`、`PUT /api/watchlist/{stock_id}/groups`、`DELETE /api/watchlist/{stock_id}/groups/{group_id}`）；編寫 API 整合測試 `pytest tests/test_watchlist_groups_api.py` 驗證通過

## 4. 自選股建議策略動態評估與最新行情同步

- [ ] 4.1 在 `backend/app/api/watchlist.py` 的自選股列表查詢中整合 `assemble_today_analysis`，動態產出 `suggested_strategy`、`entry_price`、`stop_loss`、`take_profit` 與 `trigger_condition`，並新增 `POST /api/watchlist/sync` 手動同步最新行情端點；編寫測試 `pytest tests/test_watchlist_strategy_and_sync.py` 驗證通過
- [ ] 4.2 更新 `frontend/src/api/client.ts` 與 `frontend/src/types/api.ts` 新增群組與策略點位型別定義與 API 呼叫方法；執行 `npx --prefix frontend tsc --noEmit` 驗證型別一致

## 5. 自選股多群組與建議策略前端介面

- [ ] 5.1 在 `frontend/src/components/WatchlistView.tsx` 實作群組分頁導覽標籤（「全部 (公用池)」及各群組標籤）、新增群組輸入框、每檔股票的群組標籤膠囊與「管理群組」勾選彈窗，並依當前分頁區分「移出群組」與「徹底刪除」；編寫前端組件測試驗證群組切換與標籤更新
- [ ] 5.2 在 `frontend/src/components/WatchlistView.tsx` 表格新增「建議策略」與「參考點位」欄位（進場標示策略名稱與進出場價位，觀望標示觸發條件說明），並於頂部新增「🔄 同步最新行情」按鈕與載入狀態；執行 `npm --prefix frontend test` 驗證前端測試通過

## 6. 全系統整合驗證

- [ ] 6.1 執行後端全量測試 `pytest` 確保所有測試案例通過無回歸
- [ ] 6.2 執行前端全量測試與生產打包構建 `npm --prefix frontend test` 及 `npm --prefix frontend run build`，確保無編譯錯誤與相容性問題
