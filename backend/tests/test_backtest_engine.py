"""Unit tests for backtest engine daily state machine and exit rules."""

import pandas as pd
import pytest

from app.analysis import params
from app.backtest.engine import run_backtest


def _build_df(n_days: int = 30, start_date: str = "2024-03-01", base_price: float = 100.0, atr: float = 3.0):
    """Build a baseline DataFrame with uniform prices and ATR."""
    dates = pd.date_range(start_date, periods=n_days, freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({
        "date": dates,
        "open": [base_price] * n_days,
        "high": [base_price + 1.0] * n_days,
        "low": [base_price - 1.0] * n_days,
        "close": [base_price] * n_days,
        "volume": [1000.0] * n_days,
        "atr14": [atr] * n_days,
    })


def test_signal_on_3_5_enters_on_3_6_open():
    """Requirement: 訊號日的下一個交易日開盤價作為進場成交價.

    Scenario: 3/5 訊號在 3/6 開盤進場.
    """
    df = _build_df(n_days=10, start_date="2024-03-04", base_price=100.0, atr=3.0)
    # df["date"] will be:
    # 0: 2024-03-04 (Mon)
    # 1: 2024-03-05 (Tue)
    # 2: 2024-03-06 (Wed)
    assert df.loc[1, "date"] == "2024-03-05"
    assert df.loc[2, "date"] == "2024-03-06"

    # Set 3/6 open to 102.0
    df.loc[2, "open"] = 102.0

    # Signal on 3/5 only
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[1] = True  # 3/5 close signal

    trades = run_backtest(df, signal_mask)
    # Since prices don't hit stop (102 - 6 = 96) or target (102 + 9 = 111) and df has only 10 days,
    # wait: to see completed trade, let's trigger take-profit on day 3 (3/7)
    df.loc[3, "high"] = 115.0  # triggers take profit

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_date == "2024-03-06"
    assert t.entry_price == 102.0
    # Entry at 102, ATR was 3.0 from 3/5
    # stop_loss = 102 - 2 * 3 = 96
    # take_profit = 102 + 3 * 3 = 111
    assert t.stop_loss == 96.0
    assert t.take_profit == 111.0
    assert t.exit_date == "2024-03-07"
    assert t.exit_price == 111.0
    assert t.is_win is True
    assert t.exit_reason == "take_profit"


def test_signals_during_holding_are_ignored():
    """Requirement: 不重疊持倉 - 持倉期間忽略新的進場訊號，出場後才接受下一個訊號."""
    df = _build_df(n_days=15, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))

    # Signal on day 1 (enters on day 2)
    signal_mask.iloc[1] = True
    # Subsequent signals while holding on days 2, 3, 4
    signal_mask.iloc[2] = True
    signal_mask.iloc[3] = True
    signal_mask.iloc[4] = True

    # Take profit hit on day 5
    df.loc[5, "high"] = 115.0

    # New signal AFTER exit: on day 6 (enters on day 7)
    signal_mask.iloc[6] = True
    # Take profit hit on day 8
    df.loc[8, "high"] = 115.0

    trades = run_backtest(df, signal_mask)
    # Must only have 2 trades: the one entering on day 2, and the one entering on day 7
    assert len(trades) == 2
    assert trades[0].entry_date == df.loc[2, "date"]
    assert trades[0].exit_date == df.loc[5, "date"]
    assert trades[1].entry_date == df.loc[7, "date"]
    assert trades[1].exit_date == df.loc[8, "date"]


def test_exit_rule_gap_down_below_stop_loss():
    """Scenario: 開盤跳空低於停損 - 某日開盤價已低於停損價，以該日開盤價出場並判輸."""
    df = _build_df(n_days=10, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[1] = True  # Enters day 2 (entry=100, stop=94, target=109)

    # Day 3: Gaps down at open to 91.0 (below stop 94.0)
    df.loc[3, "open"] = 91.0
    df.loc[3, "low"] = 90.0
    df.loc[3, "high"] = 92.0
    df.loc[3, "close"] = 91.5

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_date == df.loc[2, "date"]
    assert t.exit_date == df.loc[3, "date"]
    assert t.exit_price == 91.0  # Exits at OPEN price!
    assert t.exit_reason == "stop_loss_gap"
    assert t.is_win is False
    assert t.net_return < 0


def test_exit_rule_same_day_both_hit_conservative_stop_loss():
    """Scenario: 同日觸及停利與停損 - 某交易日最高價高於停利價、最低價低於停損價.

    THEN 該筆交易以停損價出場並判輸.
    """
    df = _build_df(n_days=10, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[1] = True  # Enters day 2 (entry=100, stop=94, target=109)

    # Day 3: Huge volatility touching both 93.0 (< 94) and 110.0 (> 109)
    df.loc[3, "open"] = 100.0
    df.loc[3, "low"] = 93.0
    df.loc[3, "high"] = 110.0
    df.loc[3, "close"] = 105.0

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_date == df.loc[3, "date"]
    assert t.exit_price == 94.0  # Conservative: stop loss price!
    assert t.exit_reason == "stop_loss"
    assert t.is_win is False


def test_exit_rule_intraday_stop_loss():
    """Scenario: 最低價觸及停損即以停損價出場判輸."""
    df = _build_df(n_days=10, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[1] = True  # Enters day 2 (entry=100, stop=94, target=109)

    # Day 3: low touches 93.5 (< 94.0), high only 101
    df.loc[3, "low"] = 93.5

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_price == 94.0
    assert t.exit_reason == "stop_loss"
    assert t.is_win is False


def test_exit_rule_intraday_take_profit():
    """Scenario: 最高價觸及停利即以停利價出場判贏."""
    df = _build_df(n_days=10, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[1] = True  # Enters day 2 (entry=100, stop=94, target=109)

    # Day 4: high touches 109.5 (>= 109.0)
    df.loc[4, "high"] = 109.5

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_price == 109.0
    assert t.exit_reason == "take_profit"
    assert t.is_win is True


def test_exit_rule_holding_20_days_expired_win():
    """Scenario: 持有滿 20 個交易日未觸及則以當日收盤出場，扣除成本後報酬 > 0 判贏.

    Entry at 100, day 20 close at 102.
    """
    df = _build_df(n_days=25, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[0] = True  # Enters day 1 (holding day 1)

    # Holding day 20 is index 1 + 20 - 1 = 20
    df.loc[20, "close"] = 102.0  # +2% gross, after fees net is positive
    df.loc[20, "high"] = 103.0   # does not hit target (109)
    df.loc[20, "low"] = 98.0     # does not hit stop (94)

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_date == df.loc[1, "date"]
    assert t.exit_date == df.loc[20, "date"]
    assert t.holding_days == 20
    assert t.exit_price == 102.0
    assert t.exit_reason == "max_holding_days"
    assert t.net_return > 0
    assert t.is_win is True


def test_exit_rule_holding_20_days_expired_loss():
    """Scenario: 持有滿 20 個交易日未觸及，收盤扣除成本後報酬 <= 0 判輸.

    Entry at 100, day 20 close at 99.
    """
    df = _build_df(n_days=25, start_date="2024-03-01", base_price=100.0, atr=3.0)
    signal_mask = pd.Series([False] * len(df))
    signal_mask.iloc[0] = True

    df.loc[20, "close"] = 99.0  # -1% gross -> net return negative
    df.loc[20, "high"] = 101.0
    df.loc[20, "low"] = 97.0

    trades = run_backtest(df, signal_mask)
    assert len(trades) == 1
    t = trades[0]
    assert t.holding_days == 20
    assert t.exit_price == 99.0
    assert t.exit_reason == "max_holding_days"
    assert t.net_return < 0
    assert t.is_win is False
