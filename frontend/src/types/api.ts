export interface StockLookupItem {
  stock_id: string
  stock_name: string
  name: string
  market: string
  type: string
  industry_category?: string | null
}

export interface FundamentalSummary {
  passed: boolean
  revenue_yoy: number | null
  eps_4q_sum: number | null
  debt_ratio: number | null
  reason: string
}

export interface ChipsSummary {
  passed: boolean
  foreign_trust_net_buy_10d: number | null
  margin_increase_rate_10d: number | null
  reason: string
}

export interface Trade {
  entry_date: string
  entry_price: number
  exit_date: string
  exit_price: number
  stop_loss: number
  take_profit: number
  holding_days: number
  gross_return: number
  net_return: number
  exit_reason: string
  is_win: boolean
}

export interface BacktestStats {
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number | null
  win_rate_pct: number | null
  avg_return: number | null
  avg_return_pct: number | null
  expected_value: number | null
  expected_value_pct: number | null
  avg_holding_days: number | null
  max_drawdown: number | null
  max_drawdown_pct: number | null
  insufficient_sample: boolean
  has_trades: boolean
  status_text?: string | null
}

export interface StrategyItem {
  strategy_name: string
  status: string // e.g. "進場", "觀望"
  action: string
  technical_signal: boolean
  entry_price: number | null
  stop_loss: number | null
  take_profit: number | null
  max_holding_days: number | null
  trigger_condition: string | null
  can_backtest: boolean
  backtest_message: string | null
  three_layer_stats: BacktestStats | null
  tech_only_stats: BacktestStats | null
  three_layer_trades: Trade[]
  tech_only_trades: Trade[]
}

export interface OHLCVItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface AnalysisResponse {
  stock_id: string
  stock_name: string
  evaluation_date: string
  disclaimer: string
  warnings: string[]
  fundamental: FundamentalSummary
  chips: ChipsSummary
  strategies: StrategyItem[]
  ohlcv: OHLCVItem[]
}

export interface ApiErrorData {
  code: string
  message: string
  hint?: string
}

export class ApiError extends Error {
  code: string
  hint?: string
  status: number

  constructor(status: number, data: ApiErrorData) {
    super(data.message || `API error ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.code = data.code || 'UNKNOWN_ERROR'
    this.hint = data.hint
  }
}
