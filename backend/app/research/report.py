"""Report generation utilities for factor event study in Markdown format."""

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from app.analysis.params import DISCLAIMER_TEXT
from app.research.config import StudyConfig
from app.research.event_study import FactorStat, STUDY_FACTORS
from app.research.scoring import ValidationResult

FACTOR_NAME_MAP: Dict[str, str] = {
    "strat_ma_pullback": "均線多頭拉回20MA",
    "strat_breakout_20d": "帶量突破20日新高",
    "strat_macd_cross": "MACD黃金交叉",
    "strat_kd_cross": "KD低檔黃金交叉",
    "strat_bb_breakout": "布林通道壓縮突破",
    "rev_yoy_pos": "月營收年增率 > 0%",
    "debt_ok": "季負債比 < 60%",
    "inst_net_pos": "外資投信10日買超 > 0張",
    "market_bull": "大盤多頭 (TAIEX > 60MA 且向上)",
    "vcp": "波動收斂型態 (VCP)",
    "trust_streak3": "投信連續買超 ≥ 3日",
    "inst_vol_ratio": "法人10日買超佔均量 ≥ 5%",
    "rev_accel": "月營收加速 (3m均 > 12m均)",
    "rev_new_high": "月營收創24個月新高",
    "rs_top20": "相對強度 RS (前20%強)",
}


def generate_markdown_report(
    study_res: Dict,
    val_res: ValidationResult,
    config: StudyConfig,
    stock_count: int,
    execution_seconds: float,
) -> str:
    """Generate comprehensive Markdown report from event study and validation results."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    train_stats = study_res["train_stats"]
    test_stats = study_res["test_stats"]
    train_base = study_res["train_base_hit_rate"]
    test_base = study_res["test_base_hit_rate"]
    train_n = study_res["train_sample_count"]
    test_n = study_res["test_sample_count"]
    ex = study_res["excluded_samples"]

    lines = []
    lines.append(f"# 台股選股因子事件研究與多因子驗證報告")
    lines.append(f"\n> 產生時間：`{now_str}` | 分析耗時：`{execution_seconds:.2f}` 秒")
    lines.append(f"> 宣告：**{DISCLAIMER_TEXT}**\n")

    lines.append("## 1. 研究設定與樣本概況")
    lines.append(f"- **研究標的**：本機快取共 `{stock_count}` 檔股票")
    lines.append(f"- **起漲標籤標準**：訊號日隔日開盤進場，20 個交易日內最高價曾達 `+{config.target_gain*100:.0f}%`，且在此之前未先觸及 `-{config.stop_loss*100:.0f}%`")
    lines.append(f"- **時間切分**：")
    lines.append(f"  - 訓練期 (Train)：至 `{config.train_end}`（扣除尾端 `{config.purge_days}` 個交易日空檔 Purge）")
    lines.append(f"  - 測試期 (Test Out-of-sample)：`{config.test_start}` 起完全未調參獨立驗證")
    lines.append(f"- **樣本數統計**：")
    lines.append(f"  - 訓練期有效樣本：`{train_n:,}` 筆（基準命中率：`{train_base*100:.2f}%`）")
    lines.append(f"  - 測試期有效樣本：`{test_n:,}` 筆（基準命中率：`{test_base*100:.2f}%`）")
    lines.append(f"  - 排除樣本數：硬性排除 (EPS≤0 或 融資暴增) `{ex.get('hard_exclude', 0):,}` 筆；除權息缺口 `{ex.get('dividend_or_split_gap', 0):,}` 筆；資料尾端不足 `{ex.get('insufficient_future_data', 0):,}` 筆；Purge 空檔 `{ex.get('purged', 0):,}` 筆\n")

    lines.append("## 2. 各因子單獨事件研究成果 (Lift 表)")
    lines.append("| 因子名稱 | 因子代碼 | 訓練期觸發數 | 訓練期命中率 | 訓練期 Lift (95% CI) | 測試期觸發數 | 測試期命中率 | 測試期 Lift | 權重 (log Lift) |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for factor in STUDY_FACTORS:
        name_zh = FACTOR_NAME_MAP.get(factor, factor)
        tr: FactorStat = train_stats[factor]
        te: FactorStat = test_stats[factor]
        weight = val_res.weights.get(factor, 0.0)

        tr_ci_str = f"[{tr.lift_lower:.2f}, {tr.lift_upper:.2f}]" if tr.sample_count > 0 else "-"
        tr_lift_str = f"**{tr.lift:.2f}**" if tr.lift > 1.2 else f"{tr.lift:.2f}"
        te_lift_str = f"**{te.lift:.2f}**" if te.lift > 1.2 else f"{te.lift:.2f}"
        weight_str = f"{weight:.3f}" if weight > 0 else "0.000"

        lines.append(
            f"| {name_zh} | `{factor}` | {tr.sample_count:,} | {tr.hit_rate*100:.1f}% | {tr_lift_str} {tr_ci_str} | {te.sample_count:,} | {te.hit_rate*100:.1f}% | {te_lift_str} | {weight_str} |"
        )
    lines.append("")

    lines.append("## 3. 測試期分數十分位表現 (Out-of-sample Deciles)")
    lines.append("| 分數十分位 (Decile) | 分數區間 (Score) | 樣本數 | 命中次數 | 命中率 (Hit Rate) | 表現倍數 (Lift) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    for d in val_res.decile_stats:
        d_name = f"第 {d.decile} 組（前 10% 最高分）" if d.decile == 1 else f"第 {d.decile} 組"
        lift_str = f"**{d.lift:.2f}x**" if d.decile == 1 else f"{d.lift:.2f}x"
        lines.append(
            f"| {d_name} | {d.min_score:.1f} ~ {d.max_score:.1f} | {d.sample_count:,} | {d.hit_count:,} | {d.hit_rate*100:.1f}% | {lift_str} |"
        )
    lines.append("")

    lines.append("## 4. 驗證結論與建議")
    status_icon = "✅" if val_res.passed else "❌"
    status_text = "**驗證通過 (PASS)**" if val_res.passed else "**驗證未通過 (FAIL)**"
    lines.append(f"- **測試期前 10% 分數群表現倍數 (Lift)**：`{val_res.top10_lift:.2f}` 倍（目標門檻：`≥ {config.target_lift:.1f}` 倍）")
    lines.append(f"- **前 10% 命中率**：`{val_res.top10_hit_rate*100:.1f}%`（相對於測試期全體基準 `{val_res.test_base_hit_rate*100:.1f}%`）")
    lines.append(f"- **檢驗結果**：{status_icon} {status_text}")
    lines.append("")
    if val_res.passed:
        lines.append("> [!TIP]\n> **研究成功達到 2.0 倍提升目標**。高分群對 20 日內起漲具有顯著且穩健的辨識度。可啟動後續 Change B：將多因子評分整合進入市場掃描器，並替換第一階段篩選邏輯。")
    else:
        lines.append("> [!WARNING]\n> **未達 2.0 倍門檻**。表示多因子評分在樣本外測試未能提供預期的起漲倍數提升。建議保留現有掃描器運作，並重新審視標籤定義或因子候選集合，不直接改動主程式。")
    lines.append("")

    return "\n".join(lines)
