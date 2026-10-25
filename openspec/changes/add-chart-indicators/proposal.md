# Proposal: 個股分析 K 線圖新增均線與布林通道

## Why

目前個股深度分析的 K 線圖僅繪製原始 OHLCV、成交量與回測交易進出場標記，缺乏短中長期均線與價格波動通道等常見技術參考線。使用者在評估策略訊號與歷史進出場點位時，難以直觀比對當前價格與週線 (5MA)、雙週線 (10MA)、月線 (20MA) 及布林通道上下軌的相對位置。新增這些技術指標線條與互動開關，能大幅強化波段交易決策的圖表判讀效率。

## What Changes

- **後端 API 擴充**：`/api/analysis/{stock_id}` 的 `ohlcv` 列表擴充回傳指標欄位（`ma5`, `ma10`, `ma20`, `bb_upper`, `bb_lower`, `bb_mid`），歷史早期未滿天數之暖機期回傳 `null`。
- **20MA 與布林中軌整合**：因布林中軌即為 20MA，兩者整合為同一條月線基準線，避免多線重疊混亂。
- **前端圖表渲染多線條**：在 TradingView Lightweight Charts 上疊加 5MA（琥珀黃實線）、10MA（紫色實線）、20MA（藍色實線）、布林上軌與下軌（冷灰色細虛線）。
- **圖層獨立切換開關**：K 線圖頂部新增快速開關按鈕（`[✓] 5MA`、`[✓] 10MA`、`[✓] 20MA`、`[✓] 布林通道`），預設開啟，可自由獨立勾選或關閉。
- **游標動態數值面板 (Legend)**：在圖表左上方呈現即時指標數值，隨滑鼠十字線（Crosshair）滑動即時更新當日數值，移開時自動恢復顯示最新收盤數值。

## Capabilities

### New Capabilities
無。

### Modified Capabilities
- `analysis-dashboard`: 擴充「K 線圖與標記」需求，要求支援 5MA、10MA、20MA 與布林通道線條繪製、圖層獨立開關控制與游標即時數值面板。

## Out of Scope

- 允許使用者自訂均線週期（如改成 60MA、半年線）或自訂布林通道標準差倍數。
- 在 K 線圖下方新增獨立副圖（如 MACD 柱狀圖、KD 震盪指標副圖）。
- 布林通道上下軌之間的大面積半透明區間填色。
- 其他交易市場或即時盤中分時圖支援。

## Impact

- **後端**：`backend/app/api/analysis.py` 的 `OHLCVItemModel` 擴充可選欄位；`backend/tests/test_analysis_api.py` 驗證擴充欄位正確性。
- **前端**：`frontend/src/types/api.ts` 更新 `OHLCVItem` 介面；`frontend/src/components/StockChart.tsx` 新增 LineSeries 實例管理、開關 UI 狀態與 Crosshair 數值監聽；更新 `StockChart.test.tsx`。
