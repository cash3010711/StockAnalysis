# Design

## Context

- 本機快取 `backend/data/cache.db` 目前有 132 檔股票、2021-10 ~ 2026-10 的日 K，約 15.8 萬筆，另有法人、融資、月營收、季財報資料，而且月營收與季財報已帶有 `effective_date`。
- 已有可重用的程式：`app.analysis.indicators.compute_all_indicators`（MA、ATR、MACD、KD、布林通道）、`app.analysis.strategies.evaluate_all_strategies`（5 種訊號的布林序列），以及 `app.analysis.layers.evaluate_fundamentals_series` / `evaluate_chips_series`（以 `merge_asof` 對齊的基本面與籌碼面序列）。
- `daily_k.volume` 與法人買賣超的單位都是「股」，兩者可以直接相除求比例。
- FinMind 免費帳號會從 `TaiwanStockPriceAdj` 退回到未調整的 `TaiwanStockPrice`，所以快取中的價格可能含有除權息缺口。

## Goals / Non-Goals

**Goals：**
- 用一個 CLI 指令，從本機快取跑出完整的因子 lift 表、評分與時間切分驗證結論。
- 所有計算都是向量化的 pandas 運算；132 檔的完整研究應在 2 分鐘內完成。
- 研究模組不影響現有的掃描、分析、回測行為。

**Non-Goals：**
- 不提供 API 或前端，也不把結果寫回資料庫供掃描器使用（留給 change B）。
- 不做參數搜尋或最佳化（例如在 +15% / −7% 之外再掃其他組合），避免變成研究者自己的過度擬合。

## Decisions

### D1：模組結構 — 新增 `backend/app/research/`
```
research/
  labels.py       # compute_forward_labels(df_k) -> hit / valid / excluded
  factors.py      # build_factor_panel(stock_id, repo, market_df) -> 每日布林因子 DataFrame
  event_study.py  # factor_lift_table(panel, split) -> lift / CI / n
  scoring.py      # fit_weights(train) / score(panel, weights, norm)
  report.py       # render_markdown(results) -> str
  config.py       # StudyConfig：切點、門檻、空檔天數等 dataclass
backend/scripts/run_factor_study.py   # CLI 入口（argparse）
```
**理由**：和 `analysis/` 分開，研究參數就不會汙染 `params.py`；change B 再從這裡 import 權重即可。
**替代方案**：寫成 Jupyter notebook。不採用的原因是無法測試，也無法在 change B 重用。

### D2：Panel 形式 — 長表（stock_id, date, 因子..., hit, valid）
逐檔計算後再 `concat`。132 檔 × 約 1200 日 × 約 20 欄的布林值，記憶體約 30 MB，可以接受。因子值以 pandas 的 nullable `boolean` 型別儲存，缺值為 `<NA>`。

### D3：標籤計算
- 基準價 `entry = open[t+1]`；視窗為 `t+1 … t+20`。
- 逐日掃描（numpy），找出第一個 `high ≥ entry*1.15` 的索引 `i_up` 與第一個 `low ≤ entry*0.93` 的索引 `i_dn`。`hit = i_up 存在 且 (i_dn 不存在 或 i_up < i_dn)`；如果兩者在同一天，判定為未命中。
- `valid = False` 的情況：未來資料不足 20 日而且尚未判定，或視窗內某日 `|open/prev_close − 1| > 0.105`（除權息或分割）。
- 以 `sliding_window_view` 向量化，避免在 Python 層跑雙重迴圈。

### D4：因子定義（第一批）
| 因子 | 定義 |
|---|---|
| 5 種技術訊號 | 直接沿用 `evaluate_all_strategies` |
| `rev_yoy_pos` / `debt_ok` / `inst_net_pos` | 由 `layers` 的序列取出對應欄位與門檻 |
| `market_bull` | TAIEX 收盤 > MA60 且 MA60[t] > MA60[t−20] |
| `rs_top20` | 個股 120 日報酬，當日在樣本內的橫斷面百分位 ≥ 0.8（`groupby(date).rank(pct=True)`） |
| `vcp` | ATR14/close 小於 60 日前的 ATR14/close × 0.7，且 5 日均量 < 50 日均量，且 close ≥ 250 日最高價 × 0.85 |
| `rev_accel` | 近 3 個月平均年增率 > 近 12 個月平均年增率（依 `effective_date` 對齊） |
| `rev_new_high` | 最新單月營收 ≥ 過去 24 個月的最大值 |
| `trust_streak3` | 投信淨買超連續 ≥ 3 日 |
| `inst_vol_ratio` | 外資加投信 10 日淨買超股數 ÷ (20 日均量 × 10) ≥ 0.05 |

這些門檻都寫在 `StudyConfig`，寫好之後在研究過程中**不調整**，避免利用測試期回頭修改。

### D5：TAIEX 資料
用 FinMind `TaiwanStockPrice` 搭配 `data_id="TAIEX"` 抓取，存入新的資料表 `market_index(index_id, date, close)`，並沿用 `fetch_log` 記錄增量同步進度（`stock_id="TAIEX"`, `dataset="market_index"`）。在 `DataService` 新增 `sync_market_index()`。CLI 執行前會先同步一次；同步失敗但有快取時，沿用快取並發出警告。

### D6：統計方法
- lift = p_factor / p_base，其中 p_base 是同一期間所有有效樣本的命中率。
- 信賴區間採 95% Wilson 區間；報告同時列出 lift 的下界（CI 下界 ÷ p_base），方便判斷是否顯著。
- 樣本不足門檻：訓練期觸發 n < 100 時，權重設為 0。
- 評分：`raw = Σ w_i · f_i`（缺值視為 0），正規化採訓練期 raw 的 1% 與 99% 分位數，線性映射到 0–100 並截斷。

### D7：Purge
刪除訓練期最後 20 個交易日的樣本，以 TAIEX 交易日曆計算，沒有 TAIEX 資料時改用 panel 中出現過的日期聯集。

## Risks / Trade-offs

- **倖存者偏差**：132 檔多半是使用者看過的股票，lift 可能偏高；RS 只是樣本內的相對排名。→ 報告開頭明確標註，並在全市場資料補齊後重跑。
- **樣本重疊**：相鄰日的標籤高度相關，有效樣本數比表面上少，Wilson 區間會偏窄。→ 報告註明這一點；判斷以測試期為準，不看訓練期的顯著性。
- **未調整價格**：小額除息（< 10%）無法被 D3 的缺口偵測抓到，可能讓少數樣本提早觸及 −7%。→ 這個影響對各因子是對稱的，會讓 lift 偏保守；之後如果升級成付費帳號，就改用調整後的價格。
- **測試期短**：只有約 1.8 年，涵蓋的市場狀態有限。→ 報告另外列出 2025 年上半年（關稅急跌）與之後的分段命中率。
- **因子門檻主觀**：D4 的數值是先驗設定的。→ 寫定之後不再調整；如果測試期未通過，就修改因子定義，另外開一個 change，不在這個 change 內反覆嘗試。
