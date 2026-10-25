import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StockChart } from './StockChart'
import type { OHLCVItem, StrategyItem } from '../types/api'

describe('StockChart Component', () => {
  const mockOHLCV: OHLCVItem[] = [
    {
      date: '2026-10-01',
      open: 100,
      high: 105,
      low: 99,
      close: 102,
      volume: 1000,
      ma5: null,
      ma10: null,
      ma20: null,
      bb_upper: null,
      bb_lower: null,
      bb_mid: null,
    },
    {
      date: '2026-10-05',
      open: 102,
      high: 106,
      low: 101,
      close: 105,
      volume: 1500,
      ma5: 103.5,
      ma10: null,
      ma20: null,
      bb_upper: null,
      bb_lower: null,
      bb_mid: null,
    },
    {
      date: '2026-10-20',
      open: 110,
      high: 115,
      low: 109,
      close: 114,
      volume: 2000,
      ma5: 112.0,
      ma10: 108.5,
      ma20: 105.0,
      bb_upper: 115.0,
      bb_lower: 95.0,
      bb_mid: 105.0,
    },
  ]

  const mockStrategy: StrategyItem = {
    strategy_name: '均線拉回 20MA',
    status: '進場',
    action: 'BUY',
    technical_signal: true,
    entry_price: 114,
    stop_loss: 108,
    take_profit: 125,
    max_holding_days: 20,
    trigger_condition: null,
    can_backtest: true,
    backtest_message: null,
    three_layer_stats: null,
    tech_only_stats: null,
    three_layer_trades: [],
    tech_only_trades: [],
  }

  it('renders stock chart container with indicator-expanded OHLCV data without crashing', () => {
    render(<StockChart ohlcv={mockOHLCV} />)

    expect(screen.getByTestId('stock-chart-card')).toBeInTheDocument()
    expect(screen.getByTestId('chart-container')).toBeInTheDocument()
    expect(screen.getByText('K 線圖與交易訊號')).toBeInTheDocument()
  })

  it('handles empty OHLCV array gracefully', () => {
    render(<StockChart ohlcv={[]} />)

    expect(screen.getByTestId('stock-chart-card')).toBeInTheDocument()
    expect(screen.getByTestId('chart-container')).toBeInTheDocument()
  })

  it('renders with selected strategy', () => {
    render(<StockChart ohlcv={mockOHLCV} selectedStrategy={mockStrategy} />)

    expect(screen.getByText('(當前策略：均線拉回 20MA)')).toBeInTheDocument()
  })
})
