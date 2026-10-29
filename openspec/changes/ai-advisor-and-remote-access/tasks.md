# Tasks

## 1. 網路存取與環境配置

- [ ] 1.1 更新 `backend/pyproject.toml` 與依賴清單加入 `google-genai`，並驗證 `uv sync` 能順利安裝
- [ ] 1.2 在 `backend/.env.example` 新增 `GEMINI_API_KEY=` 與說明，在 `backend/app/config.py` 加入金鑰讀取與驗證輔助函式，並執行單元測試驗證
- [ ] 1.3 調整 `frontend/vite.config.ts` 開啟 `server.host: '0.0.0.0'`，驗證在區網與本機皆可正常存取前端頁面

## 2. 後端 AI 戰略顧問模組與當日快取

- [ ] 2.1 在 `backend/app/data/cache.py` 新增 `ai_advice_cache` 資料表結構及 `get_ai_advice` / `save_ai_advice` 方法，並撰寫測試驗證讀寫與覆寫邏輯
- [ ] 2.2 實作 `backend/app/analysis/ai_advisor.py`：組裝個股量化數據 Prompt、整合 Gemini API 流式生成，並加入 API Key 缺失與異常處理機制
- [ ] 2.3 在 `backend/app/api/analysis.py` 新增 `/api/analysis/{stock_id}/ai-advice` 串流端點（支援 `force=true` 重新生成），並以單元測試驗證回傳格式與快取命中行為

## 3. 前端 AI 卡片元件與打字機流式輸出

- [ ] 3.1 於 `frontend/src/api/client.ts` 新增 AI 戰略解讀之串流呼叫方法（支援 Fetch ReadableStream / SSE 接收）
- [ ] 3.2 建立 `frontend/src/components/AiAdvisorCard.tsx` 元件，實作一鍵分析按鈕、打字機動態輸出、Markdown 排版與重新生成按鈕
- [ ] 3.3 於 `frontend/src/App.tsx` 的「個股深度分析」中整合 `AiAdvisorCard`，並撰寫前端元件測試驗證狀態切換與流式文字更新

## 4. 整合驗證與文檔更新

- [ ] 4.1 執行完整端到端測試：驗證「2330」個股點擊生成 AI 戰略、流式呈現、二次點擊讀取快取以及點擊重新生成之全流程
- [ ] 4.2 更新 `README.md`：補充 Tailscale 跨裝置連線設定指南、Gemini API 金鑰申請與配置說明，並執行全專案自動化測試套件（`uv run pytest` 與 `npm run build`）確認零迴歸

## Workflow follow-up

- 待使用者確認任務細節並同意開始實作後，執行 `openspec apply` 或 `opsx apply`。
