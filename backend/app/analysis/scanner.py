"""Market scanner pool resolution and stock screening utilities."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
import pandas as pd

from app.analysis import params
from app.analysis.assembler import assemble_today_analysis
from app.analysis.exits import calculate_exit_levels, round_to_tick
from app.analysis.indicators import compute_all_indicators
from app.analysis.strategies import evaluate_all_strategies
from app.backtest.runner import run_all_backtests
from app.data.exceptions import FinMindError, FinMindQuotaExceededError
from app.data.service import DataService
from app.data.stock_filter import format_market
from app.data.twse_client import DailyQuote, TWSEClient

TAIWAN_50_STOCKS: List[Dict[str, str]] = [
    {"stock_id": "1101", "stock_name": "台泥", "market": "上市", "type": "twse", "industry_category": "水泥工業"},
    {"stock_id": "1216", "stock_name": "統一", "market": "上市", "type": "twse", "industry_category": "食品工業"},
    {"stock_id": "1301", "stock_name": "台塑", "market": "上市", "type": "twse", "industry_category": "塑膠工業"},
    {"stock_id": "1303", "stock_name": "南亞", "market": "上市", "type": "twse", "industry_category": "塑膠工業"},
    {"stock_id": "1326", "stock_name": "台化", "market": "上市", "type": "twse", "industry_category": "塑膠工業"},
    {"stock_id": "1590", "stock_name": "亞德客-KY", "market": "上市", "type": "twse", "industry_category": "電機機械"},
    {"stock_id": "2002", "stock_name": "中鋼", "market": "上市", "type": "twse", "industry_category": "鋼鐵工業"},
    {"stock_id": "2207", "stock_name": "和泰車", "market": "上市", "type": "twse", "industry_category": "汽車工業"},
    {"stock_id": "2301", "stock_name": "光寶科", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "2303", "stock_name": "聯電", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "2308", "stock_name": "台達電", "market": "上市", "type": "twse", "industry_category": "電子零組件業"},
    {"stock_id": "2317", "stock_name": "鴻海", "market": "上市", "type": "twse", "industry_category": "其他電子業"},
    {"stock_id": "2327", "stock_name": "國巨", "market": "上市", "type": "twse", "industry_category": "電子零組件業"},
    {"stock_id": "2330", "stock_name": "台積電", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "2345", "stock_name": "智邦", "market": "上市", "type": "twse", "industry_category": "通信網路業"},
    {"stock_id": "2357", "stock_name": "華碩", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "2376", "stock_name": "技嘉", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "2379", "stock_name": "瑞昱", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "2382", "stock_name": "廣達", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "2395", "stock_name": "研華", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "2412", "stock_name": "中華電", "market": "上市", "type": "twse", "industry_category": "通信網路業"},
    {"stock_id": "2454", "stock_name": "聯發科", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "2603", "stock_name": "長榮", "market": "上市", "type": "twse", "industry_category": "航運業"},
    {"stock_id": "2609", "stock_name": "陽明", "market": "上市", "type": "twse", "industry_category": "航運業"},
    {"stock_id": "2615", "stock_name": "萬海", "market": "上市", "type": "twse", "industry_category": "航運業"},
    {"stock_id": "2880", "stock_name": "華南金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2881", "stock_name": "富邦金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2882", "stock_name": "國泰金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2883", "stock_name": "凱基金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2884", "stock_name": "玉山金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2885", "stock_name": "元大金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2886", "stock_name": "兆豐金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2887", "stock_name": "台新金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2890", "stock_name": "永豐金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2891", "stock_name": "中信金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2892", "stock_name": "第一金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "2912", "stock_name": "統一超", "market": "上市", "type": "twse", "industry_category": "貿易百貨業"},
    {"stock_id": "3008", "stock_name": "大立光", "market": "上市", "type": "twse", "industry_category": "光電業"},
    {"stock_id": "3017", "stock_name": "奇鋐", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "3034", "stock_name": "聯詠", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "3037", "stock_name": "欣興", "market": "上市", "type": "twse", "industry_category": "電子零組件業"},
    {"stock_id": "3045", "stock_name": "台灣大", "market": "上市", "type": "twse", "industry_category": "通信網路業"},
    {"stock_id": "3231", "stock_name": "緯創", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
    {"stock_id": "3661", "stock_name": "世芯-KY", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "3711", "stock_name": "日月光投控", "market": "上市", "type": "twse", "industry_category": "半導體業"},
    {"stock_id": "4904", "stock_name": "遠傳", "market": "上市", "type": "twse", "industry_category": "通信網路業"},
    {"stock_id": "5880", "stock_name": "合庫金", "market": "上市", "type": "twse", "industry_category": "金融保險業"},
    {"stock_id": "6488", "stock_name": "環球晶", "market": "上櫃", "type": "tpex", "industry_category": "半導體業"},
    {"stock_id": "6505", "stock_name": "台塑化", "market": "上市", "type": "twse", "industry_category": "油電燃氣業"},
    {"stock_id": "6669", "stock_name": "緯穎", "market": "上市", "type": "twse", "industry_category": "電腦及周邊設備業"},
]

_TAIWAN_50_MAP: Dict[str, Dict[str, str]] = {item["stock_id"]: item for item in TAIWAN_50_STOCKS}


@dataclass
class ScanFilterConfig:
    """Configuration for market scanner pool and screening conditions."""

    pool: str = "cached"  # "cached" | "tw50" | "industry" | "all" | "twse" | "tpex"
    industry_category: Optional[str] = None
    sync_latest: bool = False
    require_fundamental: bool = True
    require_chips: bool = True
    require_above_ma60: bool = False
    strategies: List[str] = field(default_factory=lambda: list(params.ALL_STRATEGIES))
    limit: Optional[int] = None
    two_stage: bool = False  # Enable two-stage all-market fast screening
    scan_date: Optional[str] = None  # Specific date YYYY-MM-DD
    min_volume_lots: float = 1000.0  # Stage 1 volume threshold in lots (張)
    min_price: float = 10.0  # Stage 1 price threshold
    top_candidates: int = 50  # Top candidates to advance to stage 2

    def __post_init__(self):
        if not self.strategies:
            self.strategies = list(params.ALL_STRATEGIES)


TECH_FILTER_VALUES = {"tech", "科技股", "科技股（電子八大類）"}
NON_TECH_FILTER_VALUES = {"non_tech", "非科技股"}


def matches_industry_filter(category: Optional[str], ind_filter: Optional[str]) -> bool:
    """Check if stock industry_category matches the given filter."""
    if not ind_filter or not ind_filter.strip():
        return True
    cleaned = ind_filter.strip()
    cat = (category or "").strip()
    if cleaned in TECH_FILTER_VALUES:
        return cat in params.TECH_INDUSTRIES
    if cleaned in NON_TECH_FILTER_VALUES:
        return bool(cat) and cat not in params.TECH_INDUSTRIES and "ETF" not in cat.upper()
    return cat == cleaned


def _enrich_stock_metadata(service: DataService, stock_id: str) -> Dict[str, str]:
    """Resolve metadata for a stock_id from DB cache, fallback to TAIWAN_50_STOCKS, or defaults."""
    db_meta = service.repo.get_stock_metadata(stock_id)
    fallback = _TAIWAN_50_MAP.get(stock_id)

    if db_meta:
        raw_type = db_meta.get("type") or (fallback["type"] if fallback else "twse")
        return {
            "stock_id": stock_id,
            "stock_name": db_meta.get("stock_name") or (fallback["stock_name"] if fallback else stock_id),
            "market": format_market(raw_type),
            "type": raw_type,
            "industry_category": db_meta.get("industry_category") or (fallback["industry_category"] if fallback else ""),
        }
    if fallback:
        return dict(fallback)
    return {
        "stock_id": stock_id,
        "stock_name": stock_id,
        "market": "上市",
        "type": "twse",
        "industry_category": "",
    }


def resolve_scan_pool(
    service: DataService,
    config: ScanFilterConfig,
    twse_client: Optional[TWSEClient] = None,
) -> List[Dict[str, str]]:
    """Resolve the target stock pool according to config.pool and config.industry_category.

    Supported pools:
    - 'cached': Stocks that currently have local daily_k data in SQLite
    - 'tw50': Built-in 50 representative Taiwan common stocks
    - 'industry': Supported common stocks in the specified industry_category
    - 'all': All supported common stocks (TWSE + TPEx)
    - 'twse': Supported TWSE (上市) common stocks
    - 'tpex': Supported TPEx (上櫃) common stocks
    """
    # Two-Stage Pipeline fast screening
    if config.two_stage:
        client = twse_client or TWSEClient()
        target_date = config.scan_date or datetime.now().strftime("%Y-%m-%d")
        quotes = client.fetch_all_quotes(target_date)
        candidates = client.filter_candidates(
            quotes,
            min_volume_lots=config.min_volume_lots,
            min_price=config.min_price,
            top_n=config.top_candidates,
        )
        if candidates:
            stocks = []
            for q in candidates:
                meta = _enrich_stock_metadata(service, q.stock_id)
                if meta.get("stock_name") == q.stock_id and q.stock_name:
                    meta["stock_name"] = q.stock_name
                stocks.append(meta)
            if config.industry_category:
                stocks = [
                    s for s in stocks
                    if matches_industry_filter(s.get("industry_category"), config.industry_category)
                ]
            if config.limit is not None and config.limit > 0:
                stocks = stocks[: config.limit]
            return stocks

    pool = (config.pool or "cached").strip().lower()
    ind_filter = config.industry_category.strip() if config.industry_category else None

    # If querying market-wide or industry pools and stock_info is empty (or sync_latest is enabled),
    # try syncing stock_info gracefully.
    if pool in ("industry", "all", "twse", "tpex"):
        if config.sync_latest or not service.repo.get_supported_stocks():
            try:
                service.sync_stock_info(max_age_days=7)
            except FinMindError:
                pass
            except Exception:
                pass

    stocks: List[Dict[str, str]] = []

    if pool == "cached":
        cached_ids = service.repo.get_cached_stock_ids()
        stocks = [_enrich_stock_metadata(service, sid) for sid in cached_ids]
        if ind_filter:
            stocks = [s for s in stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]

    elif pool == "tw50":
        stocks = [_enrich_stock_metadata(service, item["stock_id"]) for item in TAIWAN_50_STOCKS]
        if ind_filter:
            stocks = [s for s in stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]

    elif pool == "industry":
        if ind_filter in TECH_FILTER_VALUES or ind_filter in NON_TECH_FILTER_VALUES:
            all_stocks = service.repo.get_supported_stocks()
            stocks = [s for s in all_stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]
        else:
            stocks = service.repo.get_supported_stocks(industry_category=ind_filter)
        if not stocks and not service.repo.get_supported_stocks():
            # Fallback to TAIWAN_50_STOCKS when stock_info table is empty
            stocks = [dict(item) for item in TAIWAN_50_STOCKS]
            if ind_filter:
                stocks = [s for s in stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]

    elif pool == "all":
        if ind_filter in TECH_FILTER_VALUES or ind_filter in NON_TECH_FILTER_VALUES:
            all_stocks = service.repo.get_supported_stocks()
            stocks = [s for s in all_stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]
        else:
            stocks = service.repo.get_supported_stocks(industry_category=ind_filter)
        if not stocks and not service.repo.get_supported_stocks():
            stocks = [dict(item) for item in TAIWAN_50_STOCKS]
            if ind_filter:
                stocks = [s for s in stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]

    elif pool == "twse":
        if ind_filter in TECH_FILTER_VALUES or ind_filter in NON_TECH_FILTER_VALUES:
            all_stocks = service.repo.get_supported_stocks(market_type="twse")
            stocks = [s for s in all_stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]
        else:
            stocks = service.repo.get_supported_stocks(industry_category=ind_filter, market_type="twse")
        if not stocks and not service.repo.get_supported_stocks():
            stocks = [dict(item) for item in TAIWAN_50_STOCKS if item.get("type") == "twse"]
            if ind_filter:
                stocks = [s for s in stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]

    elif pool == "tpex":
        if ind_filter in TECH_FILTER_VALUES or ind_filter in NON_TECH_FILTER_VALUES:
            all_stocks = service.repo.get_supported_stocks(market_type="tpex")
            stocks = [s for s in all_stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]
        else:
            stocks = service.repo.get_supported_stocks(industry_category=ind_filter, market_type="tpex")
        if not stocks and not service.repo.get_supported_stocks():
            stocks = [dict(item) for item in TAIWAN_50_STOCKS if item.get("type") == "tpex"]
            if ind_filter:
                stocks = [s for s in stocks if matches_industry_filter(s.get("industry_category"), ind_filter)]

    else:
        raise ValueError(f"Unsupported scan pool: {config.pool}")

    if config.limit is not None and config.limit > 0:
        stocks = stocks[: config.limit]

    return stocks


def scan_single_stock(
    service: DataService,
    stock: Union[str, Dict[str, str]],
    config: ScanFilterConfig,
    quota_exceeded_session: bool = False,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Screen a single stock using the two-stage fast pipeline.

    Stage 1:
      - Synchronize latest data if requested and not in quota circuit-breaker mode.
      - Vectorized technical indicators & strategy evaluation.
      - If no requested strategy triggers on the last closed trading day, short-circuit immediately.

    Stage 2:
      - Point-in-Time 3-layer evaluation (fundamentals & chips).
      - Check user filter requirements (require_fundamental, require_chips).
      - Compute entry, stop-loss, take-profit prices and holding days.
      - Historical backtest run ONLY for triggered strategies.
      - Select best strategy win rate / avg return according to filter semantics.

    Returns:
      (matched_data_dict_or_None, quota_hit_boolean)
    """
    stock_meta = _enrich_stock_metadata(service, stock) if isinstance(stock, str) else stock
    stock_id = stock_meta["stock_id"]
    quota_hit = False

    # Sync latest data if requested and not in quota circuit-breaker mode
    if config.sync_latest and not quota_exceeded_session:
        try:
            sync_result = service.sync_stock(stock_id)
            if sync_result.quota_exceeded:
                quota_hit = True
        except FinMindQuotaExceededError:
            quota_hit = True
        except Exception:
            # Continue scanning with local cache on any sync errors
            pass

    daily_k = service.repo.get_daily_k(stock_id)
    if daily_k.empty or len(daily_k) < 35:
        return None, quota_hit

    # Stage 1: Vectorized Fast Pre-check on technical signals
    df_ind = compute_all_indicators(daily_k)
    strat_signals = evaluate_all_strategies(df_ind)

    # Check last closed trading day
    triggered_strategies = [
        strat for strat in config.strategies
        if strat in strat_signals and bool(strat_signals[strat].iloc[-1])
    ]

    # If no configured strategy triggered, short-circuit immediately
    if not triggered_strategies:
        return None, quota_hit

    # Stage 2: Point-in-Time 3-layer evaluation & backtest for triggered strategies
    eval_row = df_ind.iloc[-1]
    eval_date = str(eval_row["date"])
    close = float(eval_row["close"])
    atr14 = float(eval_row["atr14"]) if pd.notna(eval_row.get("atr14")) else 0.0

    data = service.as_of(stock_id, eval_date)
    today_analysis = assemble_today_analysis(
        stock_id=stock_id,
        daily_k=daily_k,
        monthly_revenue=data.get("monthly_revenue", pd.DataFrame()),
        quarterly_financials=data.get("quarterly_financials", pd.DataFrame()),
        institutional_investors=data.get("institutional_investors", pd.DataFrame()),
        margin_short=data.get("margin_short", pd.DataFrame()),
    )

    # Check fundamental condition if required
    if config.require_fundamental and not today_analysis.fundamental.passed:
        return None, quota_hit

    # Check chips condition if required
    if config.require_chips and not today_analysis.chips.passed:
        return None, quota_hit

    # Check 60MA condition if required
    if config.require_above_ma60:
        ma60_val = eval_row.get("ma60")
        if pd.isna(ma60_val) or close < float(ma60_val):
            return None, quota_hit

    # Compute entry / exit levels
    entry_price = round_to_tick(close)
    stop_loss, take_profit, max_holding_days = calculate_exit_levels(close, atr14)
    risk = max(0.0, entry_price - stop_loss)
    reward = max(0.0, take_profit - entry_price)
    risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0.0

    # Run historical backtests ONLY for triggered strategies
    backtest_summary = run_all_backtests(
        stock_id=stock_id,
        daily_k=daily_k,
        monthly_revenue=data.get("monthly_revenue", pd.DataFrame()),
        quarterly_financials=data.get("quarterly_financials", pd.DataFrame()),
        institutional_investors=data.get("institutional_investors", pd.DataFrame()),
        margin_short=data.get("margin_short", pd.DataFrame()),
        strategy_names=triggered_strategies,
    )

    # Calculate best win rate and avg return
    # If 3-layer conditions required, prefer three_layer stats; if relaxed or no 3-layer trades, fallback to tech_only
    best_strat_name: Optional[str] = triggered_strategies[0] if triggered_strategies else None
    best_win_rate_pct: Optional[float] = None
    best_avg_return_pct: Optional[float] = None

    use_three_layer = config.require_fundamental and config.require_chips
    strategy_stats: List[Dict[str, Any]] = []

    candidates: List[Tuple[str, Optional[float], Optional[float]]] = []

    for res in backtest_summary.results:
        st_three = res.three_layer
        st_tech = res.tech_only

        chosen = None
        if use_three_layer and st_three and st_three.has_trades and st_three.win_rate_pct is not None:
            chosen = st_three
        elif st_tech and st_tech.has_trades and st_tech.win_rate_pct is not None:
            chosen = st_tech

        w_rate = chosen.win_rate_pct if chosen else None
        avg_ret = chosen.avg_return_pct if chosen else None

        candidates.append((res.strategy_name, w_rate, avg_ret))

        strategy_stats.append({
            "strategy_name": res.strategy_name,
            "can_backtest": res.can_backtest,
            "three_layer_win_rate_pct": st_three.win_rate_pct if st_three else None,
            "three_layer_avg_return_pct": st_three.avg_return_pct if st_three else None,
            "tech_only_win_rate_pct": st_tech.win_rate_pct if st_tech else None,
            "tech_only_avg_return_pct": st_tech.avg_return_pct if st_tech else None,
        })

    # Pick the best candidate (highest win rate, then highest avg return)
    valid_candidates = [c for c in candidates if c[1] is not None]
    if valid_candidates:
        valid_candidates.sort(key=lambda c: (c[1], c[2] if c[2] is not None else -9999.0), reverse=True)
        best_strat_name = valid_candidates[0][0]
        best_win_rate_pct = valid_candidates[0][1]
        best_avg_return_pct = valid_candidates[0][2]
    elif triggered_strategies:
        best_strat_name = triggered_strategies[0]

    matched_data = {
        "stock_id": stock_id,
        "stock_name": stock_meta.get("stock_name") or service.get_stock_name(stock_id) or stock_id,
        "market": stock_meta.get("market") or "上市",
        "type": stock_meta.get("type") or "twse",
        "industry_category": stock_meta.get("industry_category") or "",
        "close": close,
        "evaluation_date": eval_date,
        "triggered_strategies": triggered_strategies,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "max_holding_days": max_holding_days,
        "risk_reward_ratio": risk_reward_ratio,
        "fundamental_passed": today_analysis.fundamental.passed,
        "revenue_yoy": today_analysis.fundamental.revenue_yoy,
        "eps_4q_sum": today_analysis.fundamental.eps_4q_sum,
        "debt_ratio": today_analysis.fundamental.debt_ratio,
        "fundamental_reason": today_analysis.fundamental.reason,
        "chips_passed": today_analysis.chips.passed,
        "foreign_trust_net_buy_10d": today_analysis.chips.foreign_trust_net_buy_10d,
        "margin_increase_rate_10d": today_analysis.chips.margin_increase_rate_10d,
        "chips_reason": today_analysis.chips.reason,
        "best_strategy_name": best_strat_name,
        "best_win_rate_pct": best_win_rate_pct,
        "best_avg_return_pct": best_avg_return_pct,
        "strategy_stats": strategy_stats,
    }

    return matched_data, quota_hit


def iter_scan_events(
    service: DataService,
    config: ScanFilterConfig,
    twse_client: Optional[TWSEClient] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Iterate through the scan pool, yielding start, match, progress, and done events."""
    stocks = resolve_scan_pool(service, config, twse_client=twse_client)
    total = len(stocks)

    yield {
        "event": "start",
        "total": total,
        "pool": config.pool,
        "sync_latest": config.sync_latest,
    }

    if total == 0:
        yield {
            "event": "done",
            "total": 0,
            "scanned": 0,
            "matched_count": 0,
            "quota_exceeded": False,
            "warnings": [],
        }
        return

    quota_exceeded_session = False
    warnings: List[str] = []
    matched_count = 0
    scanned = 0

    for idx, stock in enumerate(stocks, start=1):
        stock_id = stock.get("stock_id", "")
        stock_name = stock.get("stock_name", "")

        matched_data, quota_hit = scan_single_stock(
            service=service,
            stock=stock,
            config=config,
            quota_exceeded_session=quota_exceeded_session,
        )

        if quota_hit and not quota_exceeded_session:
            quota_exceeded_session = True
            warn = "FinMind API 請求額度已達上限，後續標的已自動降級為本機快取模式"
            if warn not in warnings:
                warnings.append(warn)

        scanned = idx

        if matched_data is not None:
            matched_count += 1
            yield {
                "event": "match",
                "data": matched_data,
                "current": scanned,
                "total": total,
                "matched_count": matched_count,
            }

        yield {
            "event": "progress",
            "current": scanned,
            "total": total,
            "stock_id": stock_id,
            "stock_name": stock_name,
            "matched_count": matched_count,
            "quota_exceeded": quota_exceeded_session,
        }

    yield {
        "event": "done",
        "total": total,
        "scanned": scanned,
        "matched_count": matched_count,
        "quota_exceeded": quota_exceeded_session,
        "warnings": warnings,
    }


def run_scan(
    service: DataService,
    config: ScanFilterConfig,
    twse_client: Optional[TWSEClient] = None,
) -> Dict[str, Any]:
    """Run full market scan synchronously and return collected results."""
    matched_results: List[Dict[str, Any]] = []
    quota_exceeded = False
    warnings: List[str] = []
    total = 0
    scanned = 0

    for event in iter_scan_events(service, config, twse_client=twse_client):
        ev = event.get("event")
        if ev == "start":
            total = event.get("total", 0)
        elif ev == "match":
            matched_results.append(event["data"])
        elif ev == "progress":
            scanned = event.get("current", scanned)
            if event.get("quota_exceeded"):
                quota_exceeded = True
        elif ev == "done":
            total = event.get("total", total)
            scanned = event.get("scanned", scanned)
            if event.get("quota_exceeded"):
                quota_exceeded = True
            for w in event.get("warnings", []):
                if w not in warnings:
                    warnings.append(w)

    return {
        "total": total,
        "scanned": scanned,
        "matched_count": len(matched_results),
        "quota_exceeded": quota_exceeded,
        "warnings": warnings,
        "results": matched_results,
    }


def run_two_stage_scan(
    service: DataService,
    twse_client: Optional[TWSEClient] = None,
    scan_date: Optional[str] = None,
    min_volume_lots: float = 1000.0,
    min_price: float = 10.0,
    top_candidates: int = 50,
    strategies: Optional[List[str]] = None,
    require_fundamental: bool = True,
    require_chips: bool = True,
    require_above_ma60: bool = False,
) -> Dict[str, Any]:
    """Execute the full two-stage market scan workflow:

    1. Broad screening using TWSE/TPEx daily quote summaries.
    2. Deep analysis with FinMind incremental sync and 3-layer verification for candidates.
    Returns scan results with calculated exit levels and backtest win rates.
    """
    config = ScanFilterConfig(
        pool="all",
        two_stage=True,
        scan_date=scan_date,
        sync_latest=True,
        require_fundamental=require_fundamental,
        require_chips=require_chips,
        require_above_ma60=require_above_ma60,
        strategies=strategies if strategies else list(params.ALL_STRATEGIES),
        min_volume_lots=min_volume_lots,
        min_price=min_price,
        top_candidates=top_candidates,
    )
    return run_scan(service, config, twse_client=twse_client)
