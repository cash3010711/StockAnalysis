# Design: 自選股追蹤與進階圖表分析

## Context

見 `proposal.md`。當前系統已具備單股三層深度分析、全市場極速快取掃描、以及主圖 5/10/20MA 與布林通道圖層。然而選股後的持續追蹤缺乏「自選股」清單落地；同時波段分析缺乏生命線（60MA/120MA）、籌碼主力動態（三大法人柱狀圖）與歷史權益波動（Equity Curve & MDD）等核心研判工具。

## Goals / Non-Goals

**Goals:**
- 提供以 SQLite 為持久化儲存的自選股清單（Watchlist），支援跨頁面一鍵收藏與追蹤。
- 擴充 60MA（季線）與 120MA（半年線）指標，支援獨立開關切換與選股多頭過濾。
- 於 K 線主圖下方新增獨立籌碼副圖，呈現外資、投信近 30 日買賣超柱狀圖。
- 在策略比較表中提供各策略歷史累積權益曲線（Equity Curve）與最大回撤（MDD）展開走勢圖。

**Non-Goals:**
- 不做即時盤中逐筆即時推播（維持收盤後日線分析架構）。
- 不實作券商下單或自動串接交易 API。

## Decisions

### 1. 自選股資料模型與 SQLite 持久化
- **決策**：於 `backend/app/data/cache.py` 中新增 `watchlist` 表：
  ```sql
  CREATE TABLE IF NOT EXISTS watchlist (
      stock_id TEXT PRIMARY KEY,
      stock_name TEXT NOT NULL,
      added_date TEXT NOT NULL,
      added_price REAL NOT NULL,
      notes TEXT DEFAULT '',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **理由**：相較於瀏覽器 `localStorage`，後端 SQLite 資料庫可直接與未來夜間自動排程深度聯動，進行每日定時狀態檢查與出場警示。

### 2. 60MA / 120MA 視覺呈現與選股連動
- **配色與樣式**：
  - 60MA（季線）：森林綠色 (`#10b981`，實線 1.5px)
  - 120MA（半年線）：磚紅色 (`#c2410c`，實線 1.5px)
- **預設狀態**：預設關閉（`false`），避免初次載入線條過於繁複；使用者點擊開啟後即刻繪製並將數值納入頂部動態 Legend。
- **選股整合**：在 `ScanFilterConfig` 與選股面板新增 `require_above_ma60: bool`，要求收盤價 `>= 60MA`。

### 3. 三大法人近 30 日買賣超副圖（Sub-pane）
- **決策**：在 `StockChart.tsx` 底部副圖建立法人買賣超柱狀圖（HistogramSeries），支援切換「成交量」或「三大法人」顯示模式。
- **資料來源**：`backend/app/api/analysis.py` 回傳擴充最近 30 交易日的三大法人淨買賣超序列（外資、投信、自營商）。

### 4. 累積權益曲線（Equity Curve）與最大回撤（MDD）走勢
- **資料組裝**：後端回測引擎 `run_backtest_with_trades` 在輸出統計時，同步產生標準化累積報酬走勢陣列 `[{ date: str, equity: float, drawdown: float }]`（初始 1.0）。
- **前端呈現**：於 `StrategyTable.tsx` 點擊任一策略列時向下展開卡片，對比展示「三層檢驗」與「純技術面」累積權益圖，直觀展現風控效益。

## Risks / Trade-offs

- **[Risk]** 新上市股票歷史天數不足 60 或 120 天。
  - **Mitigation**：前段階段自動填入 `None`，前端平滑過濾排除 `null` 值，避免線條崩落或例外。
- **[Risk]** 回測權益曲線資料量過大影響單股 API 回應速度。
  - **Mitigation**：僅針對歷史已實現交易點位採非同步/依需求展開，或壓縮只回傳交易日權益點，保證傳輸體積 < 10KB。
