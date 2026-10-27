"""CLI script to execute the stock factor event study and scoring validation."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.data.cache import CacheRepository
from app.data.service import DataService
from app.research.config import StudyConfig
from app.research.event_study import run_event_study
from app.research.factors import build_panel
from app.research.report import generate_markdown_report
from app.research.scoring import evaluate_scoring_system


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Run Taiwan stock factor event study and validation.")
    parser.add_argument("--train-end", type=str, default="2024-12-31", help="End date for training period (YYYY-MM-DD)")
    parser.add_argument("--test-start", type=str, default="2025-01-01", help="Start date for test period (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=None, help="Output path for Markdown report")
    parser.add_argument("--skip-index-sync", action="store_true", help="Skip syncing TAIEX index from FinMind")
    args = parser.parse_args()

    repo = CacheRepository()
    try:
        cached_ids = repo.get_cached_stock_ids()
        if not cached_ids:
            print("[ERROR] 本機快取中無任何股票日 K 資料，請先執行同步或查詢標的。", file=sys.stderr)
            sys.exit(1)

        print(f"[*] 找到 {len(cached_ids)} 檔本機快取股票標的")

        # Sync TAIEX index if not skipped
        if not args.skip_index_sync:
            print("[*] 正在同步/檢查加權指數 (TAIEX) 日線資料...")
            try:
                service = DataService(repo=repo)
                service.sync_market_index("TAIEX")
                print("    加權指數資料已就緒")
            except Exception as e:
                print(f"    [警告] 加權指數同步略過或失敗 ({e})，沿用本機快取")

        cfg = StudyConfig(
            train_end=args.train_end,
            test_start=args.test_start,
        )

        print(f"[*] 開始計算因子面板 (Panel) ...")
        t0 = time.time()
        panel = build_panel(repo=repo, stock_ids=cached_ids, config=cfg)
        if panel.empty:
            print("[ERROR] 因子面板構建失敗（無足夠有效資料）", file=sys.stderr)
            sys.exit(1)

        print(f"    面板構建完成，共 {len(panel):,} 筆「個股 × 交易日」")

        print(f"[*] 執行事件研究統計 (Train <= {cfg.train_end}, Test >= {cfg.test_start}) ...")
        study_res = run_event_study(panel, config=cfg)

        print(f"[*] 進行多因子加權評分與樣本外驗證 ...")
        val_res = evaluate_scoring_system(
            train_df=study_res["train_df"],
            test_df=study_res["test_df"],
            train_stats=study_res["train_stats"],
            config=cfg,
        )

        exec_time = time.time() - t0

        # Generate report
        report_md = generate_markdown_report(
            study_res=study_res,
            val_res=val_res,
            config=cfg,
            stock_count=len(cached_ids),
            execution_seconds=exec_time,
        )

        # Determine output path
        if args.output:
            out_path = Path(args.output)
        else:
            reports_dir = backend_root / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = reports_dir / f"factor_study_{ts}.md"

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        # Output summary to console
        print("\n" + "=" * 60)
        print("【因子事件研究與樣本外驗證結論】")
        print(f"- 分析股票數: {len(cached_ids)} 檔")
        print(f"- 訓練期樣本: {study_res['train_sample_count']:,} 筆 | 基準命中率: {study_res['train_base_hit_rate']*100:.2f}%")
        print(f"- 測試期樣本: {study_res['test_sample_count']:,} 筆 | 基準命中率: {study_res['test_base_hit_rate']*100:.2f}%")
        print(f"- 測試期前 10% 高分群命中率: {val_res.top10_hit_rate*100:.2f}%")
        print(f"- 測試期前 10% 高分群表現倍數 (Lift): {val_res.top10_lift:.2f}x (目標門檻: >= {cfg.target_lift:.1f}x)")
        if val_res.passed:
            print(f"- 驗證結果: [通過 PASS] - 達到 2.0x 提升目標，可推進 Change B")
        else:
            print(f"- 驗證結果: [未通過 FAIL] - 未達 2.0x 目標")
        print(f"- 詳細研究報告已儲存至: {out_path}")
        print("=" * 60 + "\n")

    finally:
        repo.close()


if __name__ == "__main__":
    main()
