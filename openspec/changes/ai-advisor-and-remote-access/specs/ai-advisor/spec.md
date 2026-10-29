# ai-advisor Specification

## Purpose
整合 Google Gemini API，根據個股之技術面指標、三層濾網檢驗結果與量化進出場點位，生成結構化進出場戰略解讀與訊號警示，並提供當日分析快取與打字機流式輸出能力。

## ADDED Requirements

### Requirement: AI 戰略解讀生成
系統 SHALL 整合 Google Gemini API，在接收到指定股票代號之請求時，以該股票當日之收盤價、均線排列、三層檢驗指標（營收與法人買賣超）、起漲評分與量化進出場點位為上下文，生成結構化戰略解讀文字。

#### Scenario: 成功生成 AI 戰略解讀
- **WHEN** 使用者針對「2330」點擊生成 AI 戰略解讀且系統已配置有效之 Gemini API 金鑰
- **THEN** 系統呼叫 Gemini API 並回傳包含「進場適宜度」、「關鍵價位規劃」、「進場觸發訊號」與「失效危險訊號」之結構化 Markdown 內容

#### Scenario: 未配置 API 金鑰提示
- **WHEN** 系統環境變數中未設定 `GEMINI_API_KEY`
- **THEN** 系統回傳明確錯誤提示訊息引導使用者於 `.env` 中設定金鑰，不得導致服務例外崩潰

### Requirement: 當日分析本機快取
系統 SHALL 將各股票於各評估基準日之 AI 解讀成果持久化快取於本機 SQLite 資料庫中；當日若已存在快取記錄，系統 SHALL 優先回傳快取內容，避免重複消耗 API 請求配額，並允許使用者強制重新生成。

#### Scenario: 命中當日快取
- **WHEN** 使用者再次開啟同一檔股票之 AI 戰略卡片且今日已生成過解讀
- **THEN** 系統立即由本機快取讀取並呈現，不向 Gemini API 發出網路請求

#### Scenario: 手動強制重新生成
- **WHEN** 使用者點擊「重新解讀」按鈕
- **THEN** 系統忽略本機既有快取，重新向 Gemini API 請求最新分析並覆寫更新快取資料庫

### Requirement: 打字機即時流式輸出
系統 SHALL 支援 Server-Sent Events 或分塊資料流（Streaming），在向 Gemini API 生成解讀時，即時將產生的文字區塊串流推播至前端進行打字機式動態渲染。

#### Scenario: 即時串流動態渲染
- **WHEN** 後端開始接收到 Gemini API 產出之第一個文字 Token
- **THEN** 前端 AI 卡片立即動態逐字顯示解讀內容，無須等待整篇文章完全生成完畢
