"""Market scanner pool resolution and stock screening utilities."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.analysis import params
from app.data.exceptions import FinMindError
from app.data.service import DataService
from app.data.stock_filter import format_market

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
    strategies: List[str] = field(default_factory=lambda: list(params.ALL_STRATEGIES))
    limit: Optional[int] = None

    def __post_init__(self):
        if not self.strategies:
            self.strategies = list(params.ALL_STRATEGIES)


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


def resolve_scan_pool(service: DataService, config: ScanFilterConfig) -> List[Dict[str, str]]:
    """Resolve the target stock pool according to config.pool and config.industry_category.

    Supported pools:
    - 'cached': Stocks that currently have local daily_k data in SQLite
    - 'tw50': Built-in 50 representative Taiwan common stocks
    - 'industry': Supported common stocks in the specified industry_category
    - 'all': All supported common stocks (TWSE + TPEx)
    - 'twse': Supported TWSE (上市) common stocks
    - 'tpex': Supported TPEx (上櫃) common stocks
    """
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
            stocks = [s for s in stocks if s.get("industry_category") == ind_filter]

    elif pool == "tw50":
        stocks = [_enrich_stock_metadata(service, item["stock_id"]) for item in TAIWAN_50_STOCKS]
        if ind_filter:
            stocks = [s for s in stocks if s.get("industry_category") == ind_filter]

    elif pool == "industry":
        stocks = service.repo.get_supported_stocks(industry_category=ind_filter)
        if not stocks and not service.repo.get_supported_stocks():
            # Fallback to TAIWAN_50_STOCKS when stock_info table is empty
            stocks = [dict(item) for item in TAIWAN_50_STOCKS]
            if ind_filter:
                stocks = [s for s in stocks if s.get("industry_category") == ind_filter]

    elif pool == "all":
        stocks = service.repo.get_supported_stocks(industry_category=ind_filter)
        if not stocks and not service.repo.get_supported_stocks():
            stocks = [dict(item) for item in TAIWAN_50_STOCKS]
            if ind_filter:
                stocks = [s for s in stocks if s.get("industry_category") == ind_filter]

    elif pool == "twse":
        stocks = service.repo.get_supported_stocks(industry_category=ind_filter, market_type="twse")
        if not stocks and not service.repo.get_supported_stocks():
            stocks = [dict(item) for item in TAIWAN_50_STOCKS if item.get("type") == "twse"]
            if ind_filter:
                stocks = [s for s in stocks if s.get("industry_category") == ind_filter]

    elif pool == "tpex":
        stocks = service.repo.get_supported_stocks(industry_category=ind_filter, market_type="tpex")
        if not stocks and not service.repo.get_supported_stocks():
            stocks = [dict(item) for item in TAIWAN_50_STOCKS if item.get("type") == "tpex"]
            if ind_filter:
                stocks = [s for s in stocks if s.get("industry_category") == ind_filter]

    else:
        raise ValueError(f"Unsupported scan pool: {config.pool}")

    if config.limit is not None and config.limit > 0:
        stocks = stocks[: config.limit]

    return stocks
