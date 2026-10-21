"""Unit tests for backtest statistics and transaction costs."""

import pytest

from app.analysis import params
from app.backtest.engine import Trade, calculate_trade_return
from app.backtest.stats import BacktestStats, compute_stats


def _make_dummy_trade(is_win: bool, net_return: float, holding_days: int = 5) -> Trade:
    return Trade(
        entry_date="2024-01-02",
        entry_price=100.0,
        exit_date="2024-01-08",
        exit_price=100.0 * (1.0 + net_return),
        stop_loss=94.0,
        take_profit=109.0,
        holding_days=holding_days,
        gross_return=net_return,
        net_return=net_return,
        exit_reason="take_profit" if is_win else "stop_loss",
        is_win=is_win,
    )


def test_transaction_costs_100_to_101():
    """Requirement: 扣除交易成本 - 買進 0.1425%、賣出 0.1425%、賣出證交稅 0.3%.

    Scenario: 成本後報酬 - WHEN 進場 100 元、出場 101 元 THEN 報酬約為 +0.41%, 不是 +1%.
    """
    gross, net = calculate_trade_return(100.0, 101.0)
    assert round(gross * 100, 2) == 1.00
    # Net return should be approximately +0.41% (0.00410575)
    assert round(net * 100, 2) == 0.41
    assert 0.0040 < net < 0.0042


def test_win_rate_30_trades_18_wins():
    """Scenario: 計算勝率 - WHEN 某策略回測共 30 筆交易，其中 18 筆判贏.

    THEN 勝率顯示 60.0%，交易筆數顯示 30.
    """
    trades = []
    # 18 wins with +5%
    for _ in range(18):
        trades.append(_make_dummy_trade(is_win=True, net_return=0.05, holding_days=6))
    # 12 losses with -3%
    for _ in range(12):
        trades.append(_make_dummy_trade(is_win=False, net_return=-0.03, holding_days=4))

    stats = compute_stats(trades)

    assert stats.total_trades == 30
    assert stats.win_trades == 18
    assert stats.loss_trades == 12
    assert stats.win_rate == 0.60
    assert stats.win_rate_pct == 60.0
    assert stats.insufficient_sample is False
    assert stats.has_trades is True

    # Expected value & avg return
    # (18 * 0.05 + 12 * -0.03) / 30 = (0.90 - 0.36) / 30 = 0.54 / 30 = 0.018 (+1.8%)
    assert round(stats.avg_return, 4) == 0.0180
    assert stats.avg_return_pct == 1.80
    assert stats.expected_value == stats.avg_return
    assert stats.expected_value_pct == 1.80

    # Holding days: (18 * 6 + 12 * 4) / 30 = (108 + 48) / 30 = 156 / 30 = 5.2
    assert stats.avg_holding_days == 5.2


def test_zero_trades_handling():
    """Scenario: 沒有任何交易 - WHEN 某策略在回測期間沒有產生任何交易.

    THEN 勝率顯示「無交易」，不顯示 0%.
    """
    stats = compute_stats([])

    assert stats.total_trades == 0
    assert stats.win_trades == 0
    assert stats.loss_trades == 0
    assert stats.win_rate is None
    assert stats.win_rate_pct is None
    assert stats.avg_return is None
    assert stats.avg_return_pct is None
    assert stats.expected_value is None
    assert stats.expected_value_pct is None
    assert stats.avg_holding_days is None
    assert stats.has_trades is False
    assert stats.insufficient_sample is True
    assert stats.status_text == "無交易"


def test_insufficient_sample_warning():
    """Scenario: 交易筆數少 - WHEN 某策略回測只有 7 筆交易.

    THEN 勝率旁顯示「樣本不足，參考性低」.
    """
    trades = [_make_dummy_trade(is_win=True, net_return=0.03) for _ in range(7)]
    stats = compute_stats(trades)

    assert stats.total_trades == 7
    assert stats.insufficient_sample is True
    assert stats.status_text == "樣本不足，參考性低"


def test_max_drawdown_calculation():
    """Requirement: 最大回檔（以逐筆累積報酬計）."""
    # Trade 1: +10% -> equity = 1.10, peak = 1.10, dd = 0
    # Trade 2: -5%  -> equity = 1.10 * 0.95 = 1.045, peak = 1.10, dd = (1.10 - 1.045)/1.10 = 0.05 (5%)
    # Trade 3: -10% -> equity = 1.045 * 0.90 = 0.9405, peak = 1.10, dd = (1.10 - 0.9405)/1.10 = 0.145 (14.5%)
    # Trade 4: +20% -> equity = 0.9405 * 1.20 = 1.1286, peak = 1.1286, dd = 0
    trades = [
        _make_dummy_trade(is_win=True, net_return=0.10),
        _make_dummy_trade(is_win=False, net_return=-0.05),
        _make_dummy_trade(is_win=False, net_return=-0.10),
        _make_dummy_trade(is_win=True, net_return=0.20),
    ]

    stats = compute_stats(trades)
    # Peak is 1.10, trough is 0.9405 -> drawdown is (1.10 - 0.9405)/1.10 = 0.145
    assert round(stats.max_drawdown, 4) == 0.1450
    assert stats.max_drawdown_pct == 14.50
