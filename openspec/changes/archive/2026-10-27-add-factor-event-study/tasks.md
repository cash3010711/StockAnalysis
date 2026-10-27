# Tasks

## 1. 研究設定與標籤

- [x] 1.1 建立 `backend/app/research/__init__.py` 與 `config.py`（`StudyConfig` dataclass：切點日期、+15% / −7% / 20 日、缺口門檻 0.105、purge 20 日、樣本不足門檻 100、D4 各因子門檻）
- [x] 1.2 實作 `labels.py` 的 `compute_forward_labels`（使用 `sliding_window_view`；處理同日雙觸、資料尾端、除權缺口排除）
- [x] 1.3 撰寫 `tests/test_research_labels.py`：先漲後跌、先跌破、同日雙觸、尾端不足、缺口排除

## 2. 加權指數資料

- [x] 2.1 在 `cache.py` 新增 `market_index` 資料表，以及 `upsert_market_index` / `get_market_index`
- [x] 2.2 在 `finmind_client.py` 新增 `get_market_index("TAIEX", start, end)`；在 `service.py` 新增 `sync_market_index()`（增量、`fetch_log`、額度用盡時沿用快取）
- [x] 2.3 撰寫 `tests/test_market_index.py`：首次同步、增量同步、額度用盡時沿用快取（mock client）

## 3. 因子計算

- [x] 3.1 實作 `factors.py` 的單股因子：5 種技術訊號、`rev_yoy_pos`、`debt_ok`、`inst_net_pos`，以及硬性排除欄位（EPS ≤ 0、融資增幅 ≥ 20%），重用 `indicators`、`strategies`、`layers`
- [x] 3.2 實作新的價量與籌碼因子：`vcp`、`trust_streak3`、`inst_vol_ratio`、`market_bull`（merge TAIEX）
- [x] 3.3 實作營收因子：`rev_accel`、`rev_new_high`（依 `effective_date` 以 `merge_asof` 對齊）
- [x] 3.4 實作 `build_panel`：逐檔串接成長表，再計算橫斷面的 `rs_top20`
- [x] 3.5 撰寫 `tests/test_research_factors.py`：每個新因子各一個合成資料案例，外加一個「營收尚未公告時不得使用」的 point-in-time 測試

## 4. 事件研究與評分

- [x] 4.1 實作 `event_study.py`：時間切分與 purge、基準命中率、各因子的 n、命中率、lift、Wilson CI
- [x] 4.2 實作 `scoring.py`：`fit_weights`（log(lift)、樣本不足或 lift ≤ 1 時權重為 0）、正規化（1% / 99% 分位數）、`score`、十分位命中率、前 10% 驗證結論
- [x] 4.3 撰寫 `tests/test_research_scoring.py`：權重凍結（測試期不影響參數）、通過與未通過的判定、樣本不足的因子權重為 0

## 5. 報告與 CLI

- [x] 5.1 實作 `report.py`：輸出 Markdown（樣本範圍、排除數、因子 lift 表、權重表、十分位表、分段命中率、結論、免責聲明）
- [x] 5.2 實作 `backend/scripts/run_factor_study.py`（argparse：`--train-end`、`--test-start`、`--output`、`--skip-index-sync`；快取為空時以非零代碼結束）；把 `backend/reports/` 加入 `.gitignore`
- [x] 5.3 用本機 132 檔實際執行一次，確認執行時間 < 2 分鐘，抽查 3 筆命中樣本的標籤與原始 K 棒是否一致，並在 README 補上使用說明
- [x] 5.4 執行 `uv run pytest`，確認全部測試通過（包含既有測試，代表掃描與回測行為沒有改變）
