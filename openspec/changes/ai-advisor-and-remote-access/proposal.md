# Proposal: AI 戰略顧問與私有遠端存取

## Why
目前使用者僅能在安裝本系統的本機電腦前查看波段分析數據，缺乏在外以手機或平板隨時瀏覽的管道；同時，現有分析結果雖提供精確的量化數據與策略勝率，但對於「當下是否適合進場、需拉回何種價位切入、盤中需觀察何種關鍵訊號」仍需使用者自行解讀。透過引入 Tailscale 私有網路存取與 Google Gemini AI 戰略解讀顧問，使用者能在任何裝置上獲取清晰易懂、具體可執行的操盤建言。

## What Changes
- **新增 AI 戰略解讀能力**：整合 Google Gemini API，結合現有個股技術面指標、三層濾網與量化進出場價位，產出結構化進出場戰略分析。
- **支援當日分析快取與流式輸出**：AI 產出結果於本機 SQLite 依日期快取避免重複消耗額度，前端以打字機流式（Streaming）呈現。
- **儀表板整合 AI 專屬卡片**：於「個股深度分析」新增「🤖 AI 盤後戰略解讀」卡片與一鍵觸發按鈕。
- **跨裝置私有網路連線支援**：配置前端 Vite 與後端伺服器監聽外部連線，支援透過 Tailscale 私有 Mesh VPN 於手機/平板直接透過專屬網址安全存取。

## Out of Scope
- 本專案不部署至公開雲端平台（如 Vercel、Render 或公開網際網路），不開放公網未經驗證之存取。
- 不提供自動下單（Auto-Trading）或券商 API 串接下單功能。
- AI 解讀僅作為個人決策輔助，不提供任何形式之公開投資推薦或保證獲利承諾。

## Capabilities

### New Capabilities
- `ai-advisor`: 提供基於 Google Gemini API 的個股進出場決策解讀、關鍵點位規劃、訊號監控與當日分析本機快取能力。

### Modified Capabilities
- `analysis-dashboard`: 擴充個股深度分析儀表板，整合 AI 戰略解讀卡片、生成狀態與流式結果呈現。

## Impact
- **後端**：新增 `ai_advisor.py` 模組、新增 API 端點 `/api/analysis/{stock_id}/ai-advice`、SQLite 新增 `ai_advice_cache` 表，依賴新增 `google-genai`，`.env` 新增 `GEMINI_API_KEY`。
- **前端**：新增 `AiAdvisorCard.tsx` 元件與 API 客戶端串接；調整 `vite.config.ts` 開放主機監聽（`host: '0.0.0.0'`）。
- **架構**：現有量化指標、三層檢驗與回測邏輯完全保留，無破壞性變更（Zero Breaking Changes）。
