"""Nightly market scan scheduler using APScheduler."""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.analysis.scanner import run_two_stage_scan
from app.data.service import DataService
from app.data.twse_client import TWSEClient

logger = logging.getLogger(__name__)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Global singleton scheduler instance
_scheduler: Optional[BackgroundScheduler] = None
_default_service: Optional[DataService] = None


def get_taipei_now() -> datetime:
    """Get current datetime in Asia/Taipei timezone."""
    return datetime.now(TAIPEI_TZ)


def execute_nightly_scan(
    service: Optional[DataService] = None,
    twse_client: Optional[TWSEClient] = None,
    scan_date: Optional[str] = None,
    manual: bool = False,
) -> Dict[str, Any]:
    """Execute two-stage market scan and persist plan to SQLite.

    Skips non-trading days automatically if not manual.
    """
    srv = service or _default_service or DataService()
    now_taipei = get_taipei_now()

    if not scan_date:
        scan_date = now_taipei.strftime("%Y-%m-%d")

    # If scheduled (not manual), check if weekend
    if not manual and now_taipei.weekday() >= 5:  # 5=Saturday, 6=Sunday
        logger.info(f"Skipping scheduled scan on weekend: {scan_date}")
        return {"status": "skipped", "reason": "周末休市", "scan_date": scan_date}

    client = twse_client or TWSEClient()

    # Step 1: Run two-stage scan
    try:
        results = run_two_stage_scan(
            service=srv,
            twse_client=client,
            scan_date=scan_date,
            min_volume_lots=1000.0,
            min_price=10.0,
            top_candidates=50,
            require_fundamental=True,
            require_chips=True,
        )
    except Exception as e:
        logger.exception(f"Error during two-stage scan on {scan_date}: {e}")
        return {"status": "failed", "error": str(e), "scan_date": scan_date}

    matched_list = results.get("results", [])
    total_candidates = results.get("total", 0)

    # Step 2: Transform to nightly plan items
    plan_items: List[Dict[str, Any]] = []
    for m in matched_list:
        win_rate = 0.0
        if m.get("best_win_rate_pct") is not None:
            win_rate = round(float(m["best_win_rate_pct"]) / 100.0, 4)

        plan_items.append({
            "stock_id": m.get("stock_id", ""),
            "stock_name": m.get("stock_name", ""),
            "market": m.get("market", "上市"),
            "strategy": m.get("best_strategy_name") or (m.get("triggered_strategies", [""])[0] if m.get("triggered_strategies") else ""),
            "win_rate": win_rate,
            "trade_count": len(m.get("strategy_stats", [])),
            "entry_price": m.get("entry_price") or m.get("close", 0.0),
            "stop_loss": m.get("stop_loss") or round(m.get("close", 0.0) * 0.95, 2),
            "take_profit": m.get("take_profit") or round(m.get("close", 0.0) * 1.08, 2),
            "holding_days": m.get("max_holding_days", 20),
            "risk_reward_ratio": m.get("risk_reward_ratio", 0.0),
            "close_price": m.get("close", 0.0),
            "volume": m.get("volume", 0.0),
            "reason": f"觸發策略: {', '.join(m.get('triggered_strategies', []))}",
        })

    # Step 3: Save to repository
    now_compact = now_taipei.strftime("%Y%m%d_%H%M%S")
    plan_id = f"plan_{now_compact}"
    note = "手動補跑排程" if manual else "每日定時自動掃描 (18:30)"

    saved_plan_id = srv.repo.save_nightly_plan(
        scan_date=scan_date,
        items=plan_items,
        plan_id=plan_id,
        status="completed",
        total_candidates=total_candidates,
        notes=note,
    )

    saved_plan = srv.repo.get_nightly_plan_by_id(saved_plan_id)
    return {
        "status": "completed",
        "plan_id": saved_plan_id,
        "scan_date": scan_date,
        "selected_count": len(plan_items),
        "total_candidates": total_candidates,
        "plan": saved_plan,
    }


def _scheduled_job():
    """Wrapper for the scheduled background job."""
    logger.info("Executing scheduled nightly market scan...")
    execute_nightly_scan(manual=False)


def init_scheduler(service: Optional[DataService] = None) -> BackgroundScheduler:
    """Initialize and configure the BackgroundScheduler instance."""
    global _scheduler, _default_service
    if service is not None:
        _default_service = service

    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=TAIPEI_TZ)
        # Schedule at 18:30 Monday through Friday (Taipei time)
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=18,
            minute=30,
            timezone=TAIPEI_TZ,
        )
        _scheduler.add_job(
            _scheduled_job,
            trigger=trigger,
            id="nightly_market_scan",
            name="台股夜間全市場掃描排程",
            replace_existing=True,
        )

    return _scheduler


def start_scheduler(service: Optional[DataService] = None):
    """Start the background scheduler if not already running."""
    sched = init_scheduler(service)
    if not sched.running:
        sched.start()
        logger.info("Nightly market scan scheduler started (Mon-Fri 18:30 Taipei Time).")


def stop_scheduler():
    """Shutdown the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Nightly market scan scheduler stopped.")


def get_scheduler_status() -> Dict[str, Any]:
    """Get current scheduler running status and next run time."""
    running = _scheduler is not None and _scheduler.running
    next_run = None
    if running and _scheduler:
        job = _scheduler.get_job("nightly_market_scan")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    return {
        "running": running,
        "next_run_time": next_run,
        "cron": "0 18:30 * * 1-5 (Asia/Taipei)",
    }
