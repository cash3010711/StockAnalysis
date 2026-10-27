# Proposal

## Why

目前的選股流程有兩個問題。第一，它無法回答「掃描器選出來的股票，事後真的會漲嗎？」，因為勝率只看個股自己的歷史，樣本往往只有幾筆，而且用來挑「最佳策略」時還會產生選擇偏差。第二，各項條件都是寬鬆的二元門檻，事前沒有驗證過，不知道它們對「即將起漲」有沒有預測力。

在修改掃描器之前，要先建立一套跨股票、point-in-time 的因子事件研究，用資料判斷哪些條件真的有效。研究結果將作為後續 change「評分接入掃描器」是否繼續的關卡。

## What Changes

- 新增**起漲標籤**：訊號日（收盤後成形）的隔日開盤價為基準，若之後 20 個交易日內最高價 ≥ +15%，而且在此之前最低價沒有先跌到 −7%，則記為命中。
- 新增**因子計算模組**，所有因子都只使用當日（含）之前已公告的資料：
  - 現有條件改當作因子：營收年增率、近四季 EPS、負債比、法人 10 日買超、融資增幅，以及 5 種技術訊號。
  - 新因子：大盤多空、RS 百分位（樣本內）、波動收斂（VCP）、營收加速或營收創新高、投信連買天數、法人買超佔 20 日均量比例。
- 新增**事件研究引擎**：計算每個因子的命中率、lift 與信賴區間，並依時間切分訓練期與測試期，兩段之間保留 20 個交易日的空檔（purge）。
- 新增**評分與驗證**：以訓練期得到的 `log(lift)` 當權重，加總後正規化成 0–100 分；接著在測試期檢驗分數前 10% 的 lift 是否 ≥ 2。
- 新增**研究報告**：透過 CLI 指令產出 Markdown 報告，內容包含各因子的 lift 表、分數級距的命中率表，以及成功或失敗的結論。
- 新增**加權指數日線資料**的同步與快取，供大盤多空因子使用。

## Capabilities

### New Capabilities
- `factor-research`：起漲標籤、因子計算、事件研究（lift）、評分、時間切分驗證與研究報告產出。

### Modified Capabilities
- `market-data`：新增加權指數（TAIEX）日線資料的同步與快取需求。

## Impact

- 新增 `backend/app/research/` 模組（labels、factors、event_study、scoring、report）與 CLI 入口 `backend/scripts/run_factor_study.py`。
- `backend/app/data/finmind_client.py`、`cache.py`、`service.py`：新增 TAIEX 日線的抓取與 `market_index` 資料表。
- 重用 `app.analysis.indicators`、`app.analysis.strategies`、`app.analysis.layers` 的現有計算，不修改它們的對外行為。
- 新增依賴：無，只使用 pandas 與 numpy。
- 報告輸出到 `backend/reports/`，並加入 `.gitignore`。

## Out of Scope

- **不修改**掃描器、兩階段第一階段的篩選、API 端點或前端顯示；這些屬於後續 change（B）。
- 不更動回測引擎的 ATR 停損停利規則。
- 不做機器學習模型、移動停利、產業輪動因子。
- 不負責把全市場資料補齊；研究先以本機現有快取（約 132 檔）進行，補齊資料由夜間排程另外處理。
