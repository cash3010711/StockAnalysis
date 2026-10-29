# Design: AI 戰略顧問與私有遠端存取

## Context
本專案為台股波段策略分析儀，現有架構採用 Python FastAPI 後端、本機 SQLite 快取與 React 前端。關於功能動機請參閱 `proposal.md`。本設計聚焦於如何在「零破壞現有架構與本機排程」的前提下，實現安全跨裝置存取與 Google Gemini AI 戰略顧問整合。

## Goals / Non-Goals

**Goals:**
- 提供在手機與外部裝置透過 Tailscale 專屬 IP 安全存取本機儀表板之能力。
- 建立 `AiAdvisor` 模組，將個股之現有技術型態、三層濾網數值與量化進出場點位組裝為 Prompt，呼叫 Google Gemini API 產出操盤戰略。
- 支援 SSE (Server-Sent Events) 打字機即時串流渲染。
- 設計 SQLite `ai_advice_cache` 本機當日快取，避免重複呼叫消耗 API 額度。

**Non-Goals:**
- 不搬遷 SQLite 至雲端資料庫（如 PostgreSQL），不破壞既有 APScheduler 18:30 本機背景排程。
- 不開放公網無驗證存取，不涉及複雜的使用者註冊與 JWT 權限系統。
- 不由 AI 自行發明勝率或未經回測的停損價格，AI 必須嚴格解讀系統既有之量化數值。

## Decisions

### 1. 遠端連線：選用 Tailscale 私有網格 VPN 而非公網 PaaS 部署
- **決策**：前端 Vite 開啟 `--host 0.0.0.0`，使用者透過 Tailscale 建立私有內網直接存取本機服務。
- **理由**：
  - 本專案高度依賴本機 SQLite (`data/cache.db`) 與本地背景定時排程（APScheduler 每日 18:30 兩階段掃描）。若搬遷至 Render/Railway 等免費 PaaS，容器會因閒置而休眠，導致夜間排程失效且 SQLite 需額外付費掛載持久硬碟。
  - Tailscale 具備點對點加密、免開 NAT/路由器連接埠、零公網暴露風險，且完全免費。
- **替代方案考慮**：
  - *Cloudflare Tunnel*：需自備域名，配置較繁瑣。
  - *全上雲端 PaaS*：需改寫資料庫層且無法保障排程穩定運行。

### 2. AI 模型與 SDK 選型：Google Gemini API
- **決策**：後端採用官方 `google-genai` SDK，模型指定 `gemini-2.5-flash`（或 `gemini-1.5-flash`），金鑰自 `.env` 讀取 `GEMINI_API_KEY`。
- **理由**：Gemini Flash 模型響應速度快（< 1.5 秒首個 Token）、免費額度充足、對繁體中文及台灣金融名詞理解極佳。
- **替代方案考慮**：
  - *OpenAI GPT-4o-mini*：需付費充值 API 額度，無免費額度。
  - *Ollama 本機模型*：需消耗高階本機 GPU 顯存與算力，對手機遠端連線效能負擔大。

### 3. Prompt 設計規範：以量化為本，嚴格約束點位
- **決策**：在後端將 `assemble_today_analysis` 的完整上下文結構化注入 Prompt：
  - 收盤價、MA5/MA20/MA60、ATR14
  - 月營收年增率、近四季 EPS、負債比
  - 外資/投信近 10 日買賣超張數、融資增減比率
  - 多因子起漲評分、命中之強因子標籤
  - 系統計算之 `entry_price`、`stop_loss`、`take_profit`
  - 要求 AI 輸出 4 大核心板塊：【進場適宜度判定】、【關鍵進出場價位規劃】、【隔日進場觸發訊號】、【防守撤退與失效訊號】。
- **理由**：杜絕 AI 幻覺與點位矛盾，確保 AI 建議與系統回測成果一致。

### 4. 資料庫當日快取與串流機制
- **決策**：
  - SQLite 新增資料表 `ai_advice_cache`：`stock_id`, `eval_date`, `content`, `created_at`。
  - API 端點 `/api/analysis/{stock_id}/ai-advice` 支援 query 參數 `force=true`。
  - 串流傳輸：後端透過 `StreamingResponse(..., media_type="text/event-stream")` 逐塊回傳 Token。

## Risks / Trade-offs

- **[Risk] 使用者未配置 `GEMINI_API_KEY`**
  - → **Mitigation**: 後端在缺少金鑰時回傳標準 JSON/SSE 錯誤狀態碼，前端卡片顯示醒目導引與複製步驟，不阻礙頁面其他圖表與回測運算。
- **[Risk] Gemini API 網路偶發抖動或 Quota 限制**
  - → **Mitigation**: 限制前端按鈕防重複連擊（Debounce/Disabled），且當日已生成的結果由本機快取提供，大幅減少外部連線頻率。
- **[Risk] 外網連線安全性**
  - → **Mitigation**: Tailscale 採用 WireGuard 協定點對點加密，只有登入同一 Tailscale 帳號的個人裝置能夠連通，外界無法掃描或訪問。

## Migration Plan
1. 更新 `backend/requirements.txt` / `backend/pyproject.toml` 加入 `google-genai`。
2. 在 `backend/app/data/cache.py` 建立 `ai_advice_cache` 表與讀寫方法。
3. 實作 `backend/app/analysis/ai_advisor.py` 與 API 路由。
4. 前端開發 `AiAdvisorCard.tsx` 並整合於 `App.tsx`。
5. 更新 `frontend/vite.config.ts` 開放 `host: '0.0.0.0'`，並於 `README.md` 補齊 Tailscale 使用指引。
