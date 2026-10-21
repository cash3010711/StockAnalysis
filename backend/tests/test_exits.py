"""Unit tests for ATR exit calculation and Taiwan stock tick size rounding."""

import pytest
from app.analysis.exits import calculate_exit_levels, get_tick_size, round_to_tick


def test_calculate_exit_levels_spec_scenario():
    """Spec scenario: 收盤價 100 元，ATR(14) 為 3 元 -> 停損 94、停利 109、最長持有 20 個交易日."""
    entry_price = 100.0
    atr = 3.0

    stop_loss, take_profit, max_days = calculate_exit_levels(entry_price, atr)

    assert stop_loss == 94.0
    assert take_profit == 109.0
    assert max_days == 20


def test_tick_sizes():
    """Verify tick size steps across all Taiwan price brackets."""
    assert get_tick_size(5.0) == 0.01
    assert get_tick_size(9.99) == 0.01
    assert get_tick_size(10.0) == 0.05
    assert get_tick_size(49.95) == 0.05
    assert get_tick_size(50.0) == 0.10
    assert get_tick_size(99.9) == 0.10
    assert get_tick_size(100.0) == 0.50
    assert get_tick_size(499.5) == 0.50
    assert get_tick_size(500.0) == 1.00
    assert get_tick_size(999.0) == 1.00
    assert get_tick_size(1000.0) == 5.00
    assert get_tick_size(2500.0) == 5.00


def test_round_to_tick_boundaries():
    """Verify tick rounding across boundaries: 10, 50, 100, 500, 1000 TWD."""
    # Boundary 10 (tick changes from 0.01 to 0.05)
    assert round_to_tick(9.984) == 9.98
    assert round_to_tick(9.986) == 9.99
    assert round_to_tick(10.01) == 10.00
    assert round_to_tick(10.03) == 10.05
    assert round_to_tick(10.08) == 10.10

    # Boundary 50 (tick changes from 0.05 to 0.10)
    assert round_to_tick(49.92) == 49.90
    assert round_to_tick(49.98) == 50.00
    assert round_to_tick(50.04) == 50.00
    assert round_to_tick(50.06) == 50.10

    # Boundary 100 (tick changes from 0.10 to 0.50)
    assert round_to_tick(99.94) == 99.90
    assert round_to_tick(99.96) == 100.00
    assert round_to_tick(100.20) == 100.00
    assert round_to_tick(100.30) == 100.50

    # Boundary 500 (tick changes from 0.50 to 1.00)
    assert round_to_tick(499.20) == 499.00
    assert round_to_tick(499.80) == 500.00
    assert round_to_tick(500.40) == 500.00
    assert round_to_tick(500.60) == 501.00

    # Boundary 1000 (tick changes from 1.00 to 5.00)
    assert round_to_tick(999.40) == 999.00
    assert round_to_tick(999.60) == 1000.00
    assert round_to_tick(1002.00) == 1000.00
    assert round_to_tick(1003.00) == 1005.00
