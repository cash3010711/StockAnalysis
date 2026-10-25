# Tasks

## 1. 後端指標序列擴充與 API 測試

- [x] 1.1 擴充 `backend/app/api/analysis.py` 中的 `OHLCVItemModel` 欄位與 `analyze_stock` 組裝邏輯，將 `compute_all_indicators` 算出的 `ma5`, `ma10`, `ma20`, `bb_mid`, `bb_upper`, `bb_lower` 填入 `ohlcv` 列表（暖機期空值填入 `None`）；執行 `uv run --project backend pytest tests/test_analysis_api.py` 驗證欄位序列與型別。
- [x] 1.2 在 `backend/tests/test_analysis_api.py` 增加專屬測試案例，驗證歷史初期指標為 `None`、第 20 天起所有均線與布林值皆正確回傳；執行 `uv run --project backend pytest` 驗證後端既有測試與新測試全數通過。

## 2. 前端型別與圖表指標線條渲染

- [x] 2.1 更新 `frontend/src/types/api.ts` 的 `OHLCVItem` 介面，納入可選指標數值欄位；執行 `cd frontend; npm run build; cd ..` 驗證前端 TypeScript 型別檢查完全通過。
- [x] 2.2 在 `frontend/src/components/StockChart.tsx` 中建立 5 條 LineSeries 實例（MA5 琥珀黃實線、MA10 紫色實線、MA20 藍色實線、布林上軌與下軌冷灰色細虛線），實作過濾排除 `null` 暖機期資料之轉換邏輯並綁定至圖表；執行 `cd frontend; npm test -- --run; cd ..` 驗證圖表元件渲染無報錯。

## 3. 圖層開關控制與動態數值面板 (Legend)

- [ ] 3.1 在 `StockChart.tsx` 圖表頂部新增開關控制列按鈕（`[✓] 5MA`、`[✓] 10MA`、`[✓] 20MA`、`[✓] 布林通道`），透過狀態管理動態調用 `applyOptions({ visible })` 切換各線條之顯隱；更新 `frontend/src/components/StockChart.test.tsx` 驗證開關切換邏輯。
- [ ] 3.2 透過 `chart.subscribeCrosshairMove` 實作十字游標動態數值面板，游標懸停在特定日期時顯示當日 5MA、10MA、20MA、布林上下軌數值，移出時顯示最新收盤日數值；執行 `cd frontend; npm test -- --run; cd ..` 確認所有前端單元與整合測試通過。

## 4. 系統整合與端對端驗證

- [ ] 4.1 執行後端 pytest 全套測試與前端 vitest 全套測試，確認「個股深度分析」與「全市場選股」雙分頁在載入個股時均線與布林通道皆可正常繪製、開關流暢且無回歸錯誤。
