"""Unit tests for publication and effective date calculations."""
import pytest

from app.data.publication import (
    get_daily_effective_date,
    get_monthly_revenue_effective_date,
    get_quarterly_financials_effective_date,
    quarter_from_date,
)


def test_quarter_from_date():
    """Verify quarter deduction from report end dates."""
    assert quarter_from_date("2023-03-31") == (2023, 1)
    assert quarter_from_date("2023-06-30") == (2023, 2)
    assert quarter_from_date("2023-09-30") == (2023, 3)
    assert quarter_from_date("2023-12-31") == (2023, 4)


def test_quarterly_financials_statutory_deadlines():
    """Verify all 4 quarters fallback to statutory deadlines when no actual date is given."""
    # Q1 -> May 15
    assert get_quarterly_financials_effective_date(2023, 1) == "2023-05-15"
    # Q2 -> August 14
    assert get_quarterly_financials_effective_date(2023, 2) == "2023-08-14"
    # Q3 -> November 14
    assert get_quarterly_financials_effective_date(2023, 3) == "2023-11-14"
    # Q4 (cross-year!) -> March 31 of next year
    assert get_quarterly_financials_effective_date(2023, 4) == "2024-03-31"


def test_quarterly_financials_with_actual_date():
    """Verify actual date is prioritized when provided."""
    actual = "2023-05-02"
    assert get_quarterly_financials_effective_date(2023, 1, actual_date=actual) == "2023-05-02"


def test_monthly_revenue_default_next_month_10th():
    """Verify monthly revenue defaults to next month 10th."""
    # September revenue -> October 10
    assert get_monthly_revenue_effective_date(2024, 9) == "2024-10-10"
    # December revenue (cross-year!) -> January 10 of next year
    assert get_monthly_revenue_effective_date(2023, 12) == "2024-01-10"


def test_monthly_revenue_prioritize_actual_date():
    """Verify actual publication date is prioritized if present."""
    actual = "2024-10-08"
    assert get_monthly_revenue_effective_date(2024, 9, actual_date=actual) == "2024-10-08"


def test_daily_effective_date():
    """Daily market data is effective on the trading day."""
    assert get_daily_effective_date("2024-01-02") == "2024-01-02"
