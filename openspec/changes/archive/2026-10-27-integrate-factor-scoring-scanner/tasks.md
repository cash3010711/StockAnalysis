# Tasks

## 1. 後端即時因子評分模組

- [x] 1.1 建立 `backend/app/analysis/factor_scorer.py`，封裝實證凍結權重、正規化區間、十分位起漲率對照表與單股即時評分函數 `evaluate_stock_factor_score`
- [x] 1.2 撰寫 `backend/tests/test_factor_scorer.py`，驗證高分標的（符合 RS、突破、營收新高）、低分標的、分數範圍 [0, 100] 與十分位轉換

## 2. 兩階段初篩流水線重構

- [x] 2.1 重構 `backend/app/data/twse_client.py` 之 `filter_candidates`，新增 `sort_by` 與 `require_bullish` 參數，預設依成交量由大至小取前 N 檔，消除強制追高限制
- [x] 2.2 更新 `backend/tests/test_twse_client.py` 與 `test_two_stage_scan.py`，驗證流動性篩選模式與 legacy 模式之相容性

## 3. 掃描器與分析組裝整合

- [x] 3.1 在 `backend/app/analysis/scanner.py` 之 `scan_single_stock` 整合 `evaluate_stock_factor_score`，於 `matched_data` 加入 `factor_score`、`factor_decile`、`historical_hit_rate`、`triggered_factors`
- [x] 3.2 在 `backend/app/analysis/assembler.py` 中補充多因子評分結果輸出
- [x] 3.3 更新 `backend/tests/test_scanner.py`，驗證掃描結果包含評分欄位，且支援以 `factor_score` 排序

## 4. 前端展示與排序升級

- [x] 4.1 在 `frontend/src/types/api.ts` 擴充 `ScanMatchedStock` 與 `AnalysisResponse` 評分型別定義
- [x] 4.2 在 `frontend/src/components/MarketScanner.tsx` 新增「起漲評分」欄位，顯示分數、十分位與歷史起漲率徽章，並支援點擊欄位標題排序
- [x] 4.3 在結果列表呈現個股觸發之關鍵強因子標籤徽章（例如「RS前20%強」、「月營收創新高」、「帶量突破20日新高」）

## 5. 系統端到端驗證

- [x] 5.1 執行後端單元測試 `uv run --project backend pytest`，確保全數通過
- [x] 5.2 執行前端編譯檢查 `npm run build`，確保無型別錯誤
