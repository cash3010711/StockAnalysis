# Proposal: 自選股追蹤與進階圖表分析

## Why

使用者在完成全市場或夜間選股後，缺乏長期保存與追蹤優質標的之清單機制；同時在技術分析層面，波段交易急需 60MA 季線作為多空保護傘、三大法人買賣超副圖確認資金動能，以及累積權益曲線（Equity Curve）與最大回撤評估策略歷史穩定度。本變更將補齊交易決策到持股追蹤的完整閉環。

## What Changes

- **自選股追蹤清單（Watchlist）**：於 SQLite 建立自選股資料庫，支援在選股結果或個股頁面一鍵點擊 ⭐ 加入/移除自選股，記錄加入日期、當時價格與備註，並展示最新收盤價與損益。
- **60MA（季線）與 120MA（半年線）**：後端指標序列與 K 線圖擴充 60MA（綠色）與 120MA（磚紅色）圖層開關（預設關閉），並在選股中提供季線多頭排列過濾。
- **三大法人 30 日買賣超副圖**：在 K 線主圖下方新增獨立籌碼副圖（Sub-pane），以紅藍柱狀圖呈現外資、投信、自營商近 30 日買賣超張數，時間軸與主圖游標同步對齊。
- **累積權益曲線與最大回撤圖**：於策略比較表下方提供展開式權益曲線（Equity Curve）與回撤（Drawdown）視覺化走勢圖，直觀對比三層檢驗與純技術面歷史抗跌力。

## Capabilities

### New Capabilities
- `watchlist`: 提供自選股追蹤管理功能，包含加入/移除標的、記錄歷史點位與追蹤每日三層狀態與出場訊號。

### Modified Capabilities
- `analysis-dashboard`: 擴充個股分析儀介面，新增 60MA/120MA 圖層開關、三大法人買賣超籌碼副圖、以及策略累積權益與回撤曲線展開面板。
- `market-scanner`: 選股條件設定擴充「站上 60MA 季線」多頭趨勢過濾選項。

## Out of Scope

- 不包含自動串接券商 API 進行實盤下單或自動停損出場。
- 不支援自訂非標準週期（如 72MA 或非對稱布林通道）。
- 依專案規範僅支援 Windows 運行環境，不支援 macOS/Linux 特有服務。

## Impact

- **後端模組**：`backend/app/data/cache.py`（新增 `watchlist` 表與 CRUD）、`backend/app/analysis/indicators.py`（擴充 60MA/120MA 計算）、`backend/app/api/watchlist.py`（新增自選股端點）、`backend/app/api/analysis.py`。
- **前端介面**：新增自選股清單視圖與星號加入按鈕、升級 `StockChart.tsx` 支援副圖與均線、擴充 `StrategyTable.tsx` 支援權益曲線展開圖。
