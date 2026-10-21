"""Centralized parameters and thresholds for stock analysis and backtesting.

All thresholds specified in design.md and specs are defined here as constants.
"""

from typing import List

# Fundamental filter thresholds
REVENUE_YOY_MIN: float = 0.0  # Monthly revenue YoY must be > 0%
EPS_4Q_SUM_MIN: float = 0.0  # Sum of trailing 4 quarters EPS must be > 0 TWD
DEBT_RATIO_MAX: float = 60.0  # Most recent debt ratio must be < 60%

# Chips (institutional & margin) thresholds
INSTITUTIONAL_LOOKBACK_DAYS: int = 10  # 10 trading days lookback
INSTITUTIONAL_NET_BUY_MIN: float = 0.0  # Foreign + Investment trust net buy > 0 lots (張)
MARGIN_LOOKBACK_DAYS: int = 10  # 10 trading days lookback
MARGIN_INCREASE_RATE_MAX: float = 0.20  # Margin balance increase rate < 20%

# Technical indicator parameters
MA_FAST: int = 5
MA_MID: int = 10
MA_SLOW: int = 20

BREAKOUT_WINDOW: int = 20
VOLUME_MA_WINDOW: int = 20
VOLUME_BREAKOUT_FACTOR: float = 1.5

MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9

KD_PERIOD: int = 9
KD_SMOOTH_K: int = 3
KD_SMOOTH_D: int = 3
KD_LOW_THRESHOLD: float = 30.0

BB_WINDOW: int = 20
BB_NUM_STD: float = 2.0
BB_SQUEEZE_LOOKBACK_DAYS: int = 5
BB_PERCENTILE_WINDOW: int = 120
BB_SQUEEZE_PERCENTILE: float = 0.20
BB_VOLUME_FACTOR: float = 1.5

# Exit & Backtest parameters
ATR_WINDOW: int = 14
STOP_LOSS_ATR_MULT: float = 2.0  # Entry - 2 * ATR
TAKE_PROFIT_ATR_MULT: float = 3.0  # Entry + 3 * ATR
MAX_HOLDING_DAYS: int = 20

MIN_SAMPLE_SIZE: int = 20  # Sample size threshold for backtest warning
TRANSACTION_FEE_RATE: float = 0.001425  # 0.1425% each side
TRANSACTION_TAX_RATE: float = 0.003  # 0.3% sell side

# Strategy Identifiers and Names
STRATEGY_MA_PULLBACK: str = "均線多頭排列下拉回20MA"
STRATEGY_BREAKOUT_20D: str = "帶量突破20日新高"
STRATEGY_MACD_CROSS: str = "MACD黃金交叉"
STRATEGY_KD_CROSS: str = "KD低檔黃金交叉"
STRATEGY_BB_BREAKOUT: str = "布林通道壓縮突破"

ALL_STRATEGIES: List[str] = [
    STRATEGY_MA_PULLBACK,
    STRATEGY_BREAKOUT_20D,
    STRATEGY_MACD_CROSS,
    STRATEGY_KD_CROSS,
    STRATEGY_BB_BREAKOUT,
]

DISCLAIMER_TEXT: str = "僅供個人研究參考，非投資建議"
