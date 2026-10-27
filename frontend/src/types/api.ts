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

export interface EquityPoint {
  date: string
  equity: number
  drawdown: number
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
  equity_curve?: EquityPoint[]
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
  three_layer_equity_curve?: EquityPoint[]
  tech_only_equity_curve?: EquityPoint[]
}

export interface InstitutionalItem {
  date: string
  foreign_net: number
  investment_trust_net: number
  dealer_net: number
  total_net: number
}

export interface OHLCVItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ma5?: number | null
  ma10?: number | null
  ma20?: number | null
  ma60?: number | null
  ma120?: number | null
  bb_upper?: number | null
  bb_lower?: number | null
  bb_mid?: number | null
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
  institutional?: InstitutionalItem[]
  factor_score?: number | null
  factor_decile?: number | null
  historical_hit_rate?: number | null
  historical_lift?: number | null
  triggered_factors?: string[]
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

export interface ScanOptionPool {
  id: string
  name: string
}

export interface ScannerOptionsDefaults {
  pool: string
  industry_category: string | null
  sync_latest: boolean
  require_fundamental: boolean
  require_chips: boolean
  require_above_ma60?: boolean
  strategies: string[]
}

export interface ScannerOptionsResponse {
  pools: ScanOptionPool[]
  industries: string[]
  strategies: string[]
  cached_count: number
  defaults: ScannerOptionsDefaults
}

export interface ScanRequest {
  pool?: string
  industry_category?: string | null
  sync_latest?: boolean
  require_fundamental?: boolean
  require_chips?: boolean
  require_above_ma60?: boolean
  strategies?: string[]
  limit?: number | null
  two_stage?: boolean
  scan_date?: string | null
}

export interface WatchlistGroup {
  id: number
  name: string
  created_at?: string
}

export interface WatchlistItem {
  stock_id: string
  stock_name: string
  added_date: string
  added_price: number
  current_price?: number | null
  current_date?: string | null
  change_pct?: number | null
  return_pct?: number | null
  notes?: string
  created_at?: string
  groups?: WatchlistGroup[]
  suggested_strategy?: string | null
  entry_price?: number | null
  stop_loss?: number | null
  take_profit?: number | null
  trigger_condition?: string | null
}

export interface WatchlistSyncResponse {
  success: boolean
  synced_count: number
  total_count: number
  errors: string[]
  items?: WatchlistItem[]
}

export interface StrategyStatItem {
  strategy_name: string
  can_backtest: boolean
  three_layer_win_rate_pct?: number | null
  three_layer_avg_return_pct?: number | null
  tech_only_win_rate_pct?: number | null
  tech_only_avg_return_pct?: number | null
}

export interface ScanMatchedStock {
  stock_id: string
  stock_name: string
  market: string
  type: string
  industry_category?: string | null
  close: number
  evaluation_date: string
  triggered_strategies: string[]
  entry_price?: number | null
  stop_loss?: number | null
  take_profit?: number | null
  max_holding_days?: number | null
  risk_reward_ratio?: number | null
  fundamental_passed: boolean
  revenue_yoy?: number | null
  eps_4q_sum?: number | null
  debt_ratio?: number | null
  fundamental_reason: string
  chips_passed: boolean
  foreign_trust_net_buy_10d?: number | null
  margin_increase_rate_10d?: number | null
  chips_reason: string
  best_strategy_name?: string | null
  best_win_rate_pct?: number | null
  best_avg_return_pct?: number | null
  strategy_stats: StrategyStatItem[]
  factor_score?: number | null
  factor_decile?: number | null
  historical_hit_rate?: number | null
  historical_lift?: number | null
  triggered_factors?: string[]
}

export interface ScanRunResponse {
  total: number
  scanned: number
  matched_count: number
  quota_exceeded: boolean
  warnings: string[]
  results: ScanMatchedStock[]
}

export interface ScanStartEvent {
  event: 'start'
  total: number
}

export interface ScanMatchEvent {
  event: 'match'
  data: ScanMatchedStock
  current: number
  total: number
  matched_count: number
}

export interface ScanProgressEvent {
  event: 'progress'
  current: number
  total: number
  stock_id: string
  stock_name: string
  matched_count: number
  quota_exceeded: boolean
}

export interface ScanDoneEvent {
  event: 'done'
  total: number
  scanned: number
  matched_count: number
  quota_exceeded: boolean
  warnings: string[]
}

export type ScanStreamEvent =
  | ScanStartEvent
  | ScanMatchEvent
  | ScanProgressEvent
  | ScanDoneEvent
