# 台股波段策略分析儀 (Taiwan Stock Swing Strategy Analyzer)

提供台股（上市、上櫃普通股）波段交易策略分析與回測的本機 Web 應用工具。結合「基本面、籌碼面、技術面」三層檢驗與歷史回測統計，杜絕未來函數偏差。

---

## 系統架構

- **後端 (Backend)**: Python 3.12 + FastAPI + pandas + numpy + SQLite（套件管理：[uv](https://docs.astral.sh/uv/)）
- **前端 (Frontend)**: React 19 + TypeScript + Vite + TradingView Lightweight Charts（套件管理：npm）

---

## 申請 FinMind Token 步驟

本系統行情與財報資料來源為 FinMind 免費 API（每小時約 600 次請求額度）：

1. 前往 [FinMind 官方網站](https://finmind.github.io/) 註冊帳號。
2. 登入後至個人設定或 API 金鑰頁面取得您的 **API Token**。
3. 在專案根目錄或 `backend/` 目錄下建立 `.env` 檔案：
   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```
4. 開啟 `backend/.env`，將取得的 Token 填入：
   ```ini
   FINMIND_TOKEN=貼上您的FinMindToken
   ```

> **注意：** `.env` 與快取資料庫 `data/cache.db` 已被 `.gitignore` 排除，不會被提交至版本控制中。

---

## Windows 環境需求 (Prerequisites)

1. **Node.js** (v18 或更新版本，建議 v20+)：
   - 可至 [Node.js 官網](https://nodejs.org/) 下載安裝，確認終端機具備 `node` 與 `npm`。
2. **uv** (極速 Python 套件管理工具)：
   - 若尚未安裝，可在 PowerShell 執行：
     ```powershell
     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
     ```
   - `uv` 會自動依據專案需求下載並管理 Python 3.12，無需手動配置 Python 環境。

---

## Windows 啟動前後端步驟

### 1. 啟動後端 API 服務

開一個 PowerShell 視窗：

```powershell
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

> 第一次執行時，`uv` 會自動建立虛擬環境並安裝所有依賴套件。
> 也可以直接在專案根目錄執行：`uv run --project backend uvicorn app.main:app --reload --port 8000`

- 後端 API 網址：`http://127.0.0.1:8000`
- 健康檢查端點：[http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- API 互動文件：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. 啟動前端開發伺服器

另開一個 PowerShell 視窗：

```powershell
cd frontend
npm install
npm run dev
```

- 前端預設網址：`http://localhost:5173`（若 5173 埠號已被占用，Vite 會自動依序使用 5174）
- 前端已設定 `/api` 代理（Proxy）導向後端 `http://127.0.0.1:8000`，開啟頁面即可看到後端健康檢查狀態。

---

## 執行測試

### 後端單元測試

進入 `backend/` 目錄執行：

```powershell
cd backend
uv run pytest
```

或從專案根目錄執行：

```powershell
uv run --project backend pytest
```

### 前端編譯檢查

進入 `frontend/` 目錄執行：

```powershell
cd frontend
npm run build
```
