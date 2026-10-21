"""Security filtering rules to ensure only TWSE and TPEx common stocks are supported."""
from typing import Any, Dict


def is_supported_common_stock(
    stock_id: str,
    stock_name: str = "",
    stock_type: str = "",
    industry_category: str = "",
) -> bool:
    """Check whether a security is a supported Taiwan common stock (上市、上櫃普通股).

    Excludes:
    - Emerging stocks (興櫃, stock_type == 'emerging')
    - ETFs and ETNs (00xxx, 01xxx, 02xxx, or categories with ETF/ETN/受益證券)
    - Warrants (權證, length != 4, contains non-digits, etc.)
    - Preferred stocks (特別股, 5 chars ending with letters, or containing '甲特' etc.)
    - Indices, TDRs, and other non-common securities
    """
    stock_id = str(stock_id).strip()
    stock_name = str(stock_name).strip() if stock_name else ""
    stock_type = str(stock_type).strip().lower() if stock_type else ""
    category = str(industry_category).strip() if industry_category else ""

    # 1. Market type must be TWSE (上市) or TPEx (上櫃)
    if stock_type not in ("twse", "tpex"):
        return False

    # 2. Common stock code in TWSE/TPEx is exactly 4 digits
    if len(stock_id) != 4 or not stock_id.isdigit():
        return False

    # 3. Exclude ETF / ETN / REIT ticker prefixes (00xxx, 01xxx, 02xxx)
    if stock_id.startswith(("00", "01", "02")):
        return False

    # 4. Exclude non-common categories
    excluded_categories = (
        "ETF",
        "ETN",
        "Index",
        "大盤",
        "受益證券",
        "存託憑證",
        "所有證券",
    )
    if any(kw in category for kw in excluded_categories):
        return False

    # 5. Exclude preferred stocks (特別股)
    preferred_keywords = (
        "甲特",
        "乙特",
        "丙特",
        "丁特",
        "戊特",
        "己特",
        "庚特",
        "辛特",
        "特別股",
    )
    if any(kw in stock_name for kw in preferred_keywords):
        return False

    # Additional check: financial preferred names ending in '特'
    if stock_name.endswith("特") and any(bank in stock_name for bank in ("中信", "開發", "富邦", "國泰", "新光", "金", "銀")):
        return False

    return True


def format_market(stock_type: str) -> str:
    """Convert FinMind market type identifier to human-readable Chinese string."""
    m = str(stock_type).strip().lower()
    if m == "twse":
        return "上市"
    if m == "tpex":
        return "上櫃"
    if m == "emerging":
        return "興櫃"
    return stock_type
