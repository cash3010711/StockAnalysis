"""Publication and effective date calculation for point-in-time correctness."""
from __future__ import annotations
from datetime import date
from typing import Optional, Tuple


def get_monthly_revenue_effective_date(
    year: int,
    month: int,
    actual_date: Optional[str] = None,
) -> str:
    """Calculate effective date for monthly revenue.

    Prioritize actual publication date if available and non-empty.
    Otherwise default to the 10th day of the following month.
    """
    if actual_date and str(actual_date).strip():
        # Clean actual date string (e.g. '2026-10-08')
        cleaned = str(actual_date).strip().split(" ")[0]
        if len(cleaned) == 10 and cleaned.count("-") == 2:
            return cleaned

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    return f"{next_year:04d}-{next_month:02d}-10"


def quarter_from_date(date_str: str) -> tuple[int, int]:
    """Infer (year, quarter) from report end date string (e.g. '2023-03-31')."""
    parts = date_str.strip().split("-")
    year = int(parts[0])
    month = int(parts[1])
    quarter = (month - 1) // 3 + 1
    return year, quarter


def get_quarterly_financials_effective_date(
    year: int,
    quarter: int,
    actual_date: Optional[str] = None,
) -> str:
    """Calculate effective date for quarterly financial statements.

    Prioritize actual publication date if available.
    Otherwise fallback to statutory deadlines:
      Q1: 05-15
      Q2: 08-14
      Q3: 11-14
      Q4: 03-31 of next year
    """
    if actual_date and str(actual_date).strip():
        cleaned = str(actual_date).strip().split(" ")[0]
        if len(cleaned) == 10 and cleaned.count("-") == 2:
            return cleaned

    if quarter == 1:
        return f"{year:04d}-05-15"
    elif quarter == 2:
        return f"{year:04d}-08-14"
    elif quarter == 3:
        return f"{year:04d}-11-14"
    elif quarter == 4:
        return f"{year + 1:04d}-03-31"
    else:
        raise ValueError(f"Invalid quarter: {quarter}. Must be 1, 2, 3, or 4.")


def get_daily_effective_date(trade_date: str) -> str:
    """Daily market data (OHLCV, institutional, margin) is effective on the trade day."""
    return str(trade_date).strip()
