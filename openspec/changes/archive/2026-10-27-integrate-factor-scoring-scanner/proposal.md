# Proposal

## Why

在前期事件研究中，我們證實了多因子評分（結合 RS 相對強度、營收動能、突破型態等）在 2025 年樣本外驗證中具有高達 2.0 倍的起漲命中率（高分群 24.9% vs 全體基準 12.5%）。然而現有市場掃描器仍存在兩大問題：第一，兩階段第一階段篩選挑選「當日漲幅前 50」，嚴重過濾掉盤整起漲與拉回標的；第二，掃描結果僅依賴個股自身稀少的歷史回測勝率排序，容易產生假訊號與過度擬合。

本變更將研究成果正式整合進系統，以多因子起漲評分升級掃描器與前端展示。

## What Changes

- **兩階段掃描器第一階段重構**：新增「依多因子評分或純流動性選樣」模式，淘汰「當日漲幅由高到低」的強制追高邏輯，保留 legacy 模式供切換。
- **後端多因子即時評分與指標**：在 `scanner.py` 與 `assembler.py` 整合 `app.research.scoring`，為每檔掃描命中的個股輸出：
  - `factor_score`：0 ~ 100 分之起漲潛力評分。
  - `factor_decile`：分數所屬十分位組別（1 ~ 10）。
  - `historical_hit_rate`：該十分位組對應之跨股票 5 年驗證命中率（例如第 1 組 24.9%）。
  - `triggered_factors`：命中的關鍵加分因子標籤清單（如 RS前20%、營收新高、突破等）。
- **前端掃描儀與卡片升級**：
  - 掃描清單新增「起漲評分」欄位與徽章，支援以起漲評分由高到低排序。
  - 呈現跨股票驗證之「歷史起漲機率」，取代原本易失真的單一個股少樣本勝率。
  - 呈現個股觸發的優質因子標籤。

## Capabilities

### Modified Capabilities
- `market-scanner`：兩階段篩選邏輯修正、多因子即時評分輸出、排序與結果欄位擴充。
- `analysis-dashboard`：前端掃描器結果表格與個股卡片呈現多因子評分、歷史起漲率與因子徽章。

## Impact

- 後端：`backend/app/analysis/scanner.py`, `backend/app/data/twse_client.py`, `backend/app/api/scanner.py`, `backend/app/analysis/assembler.py`。
- 前端：`frontend/src/types/index.ts`, `frontend/src/components/ScannerTable.tsx`（或相關掃描結果視圖）。
- 不影響回測引擎與既有 API 欄位相容性。

## Out of Scope

- 不修改 FinMind 資料抓取排程或快取結構。
- 不更動個股回測的 ATR 停損停利機制。
- 不導入機器學習即時推論服務。
