# Design: 個股分析 K 線圖新增均線與布林通道

## Context

見 `proposal.md`。當前前端 `StockChart.tsx` 使用 TradingView `lightweight-charts` (v5) 繪製 K 線 (`CandlestickSeries`)、成交量 (`HistogramSeries`) 與買賣點位標記 (`createSeriesMarkers`)。後端 `backend/app/analysis/indicators.py` 原先在評估技術面時已完整計算 `ma5`、`ma10`、`ma20`、`bb_mid`、`bb_upper`、`bb_lower` 等指標，但先前 `/api/analysis/{stock_id}` 回傳的 `ohlcv` 結構僅包含標準開高低收量欄位，尚未對外提供指標數值。

## Goals / Non-Goals

**Goals:**
- 在後端 API 回傳中帶入指標歷史序列，維持前後端指標算法完全統一。
- 在前端 K 線圖上疊加渲染 5MA、10MA、20MA 與布林通道上下軌。
- 整合 20MA 與布林中軌為同一基準線，避免多線重疊混淆。
- 提供直覺的獨立開關控制列，支援單鍵切換各線條之顯示/隱藏。
- 提供隨游標（Crosshair）懸停即時更新的指標數值圖例面板（Legend）。

**Non-Goals:**
- 不支援前端自訂指標週期（如 60MA 或非 2 倍標準差之布林通道）。
- 不實作布林通道上下軌之間的滿版填色（保持 K 線與進出場箭頭標記清晰可見）。
- 不影響回測引擎與三層檢驗現有邏輯。

## Decisions

### 1. 後端擴充 OHLCV 回傳模型，而非前端在瀏覽器端重算
- **決策**：在 `backend/app/api/analysis.py` 的 `OHLCVItemModel` 中擴充可選欄位：
  ```python
  class OHLCVItemModel(BaseModel):
      date: str
      open: float
      high: float
      low: float
      close: float
      volume: int
      ma5: Optional[float] = None
      ma10: Optional[float] = None
      ma20: Optional[float] = None
      bb_upper: Optional[float] = None
      bb_lower: Optional[float] = None
      bb_mid: Optional[float] = None
  ```
  在組裝分析回應時，將 `compute_all_indicators(daily_k)` 計算出的欄位安全轉成 float（NaN 轉為 None）。
- **理由**：指標算法由後端 Python 核心統籌維護，確保前端看到的數值與後端觸發策略的數值 100% 一致，避免 JavaScript 浮點數或 rolling window 計算之雙重維護成本。

### 2. 暖機期資料空值（Null / NaN）處理
- **決策**：歷史初期天數不足的交易日（如前 4 天無 5MA、前 19 天無 20MA 與布林線），API 回傳 `null`。
- **前端繪圖策略**：前端在餵給 Lightweight Charts `LineSeries.setData()` 前，過濾排除數值為 `null` 的項目：
  ```typescript
  const ma5Data = ohlcv
    .filter(d => d.ma5 != null)
    .map(d => ({ time: d.date as Time, value: d.ma5! }))
  ```
- **理由**：Lightweight Charts 若接收無效值或 0 會造成折線向原點暴跌或中斷報錯，過濾後各線條會自然從數值生效日（第 5 / 10 / 20 日）起平滑呈現。

### 3. 20MA 與布林中軌整合
- **決策**：布林通道中軌（20 SMA）與 20MA 為同一數學定義。圖面上僅繪製一條 20MA（藍色實線 2px），圖例與面板標示為「20MA / 布林中軌」，布林通道主要繪製上軌與下軌（冷灰色細虛線 1px）。
- **理由**：避免在同一折線上繪製兩條顏色相近或重疊的線條，保持介面簡潔俐落。

### 4. 線條視覺樣式與配色
- **MA5 (週線)**：琥珀黃色 (`#f59e0b`，LineType: Simple, lineWidth: 1.5)
- **MA10 (雙週線)**：紫色 (`#a855f7`，LineType: Simple, lineWidth: 1.5)
- **MA20 (月線 / 布林中軌)**：藍色 (`#3b82f6`，LineType: Simple, lineWidth: 2)
- **布林上軌 / 下軌**：冷灰色 (`#64748b`，LineStyle: LineStyle.Dashed, lineWidth: 1)

### 5. 前端圖層開關與狀態管理
- **決策**：在 `StockChart.tsx` 建立開關狀態：
  ```typescript
  const [visibleLayers, setVisibleLayers] = useState({
    ma5: true,
    ma10: true,
    ma20: true,
    bollinger: true,
  })
  ```
  在圖表掛載時建立 5 個 `LineSeries`（MA5, MA10, MA20, BB_Upper, BB_Lower）。透過 `series.applyOptions({ visible: visibleLayers.key })` 即時響應開關切換，無需銷毀重建圖表實例。
- **解耦原則**：「MA20 開關」控制 20MA 藍色基準線；「布林通道開關」控制上軌與下軌兩條灰色虛線，兩者各自獨立。

### 6. 十字游標動態圖例 (Legend)
- **決策**：透過 `chart.subscribeCrosshairMove` 監聽游標移動事件，若游標指向特定日期，即時查找該日之各項指標數值並更新到面板；游標移出圖表時自動重置為歷史最後一筆（最新收盤日）的數值。

## Risks / Trade-offs

- **[Risk]** 在歷史交易日非常少的新上市股票（例如剛掛牌 10 天），MA20 與布林線可能整段皆為空值。
  - **Mitigation**：前端防呆處理，當過濾後資料長度為 0 時，調用 `series.setData([])`，圖表正常繪製 K 線，數值面板顯示 `-`，不產生任何例外。
- **[Risk]** Lightweight Charts 在不同視窗尺寸下重繪可能導致 Legend 面板排版位移。
  - **Mitigation**：Legend 採用 Flex 佈局放置於圖表上方控制列，不使用絕對定位覆蓋圖布，保證不同螢幕解析度下均能穩定對齊。
