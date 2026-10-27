import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StrategyTable } from './StrategyTable'
import type { StrategyItem } from '../types/api'

describe('StrategyTable component', () => {
  const mockStrategies: StrategyItem[] = [
    {
      strategy_name: '均線拉回 20MA',
      status: '進場',
      action: '進場',
      technical_signal: true,
      entry_price: 100.0,
      stop_loss: 94.0,
      take_profit: 109.0,
      max_holding_days: 20,
      trigger_condition: null,
      can_backtest: true,
      backtest_message: null,
      three_layer_stats: {
        total_trades: 25,
        win_trades: 16,
        loss_trades: 9,
        win_rate: 0.64,
        win_rate_pct: 64.0,
        avg_return: 0.035,
        avg_return_pct: 3.5,
        expected_value: 0.021,
        expected_value_pct: 2.1,
        avg_holding_days: 8.5,
        max_drawdown: -0.065,
        max_drawdown_pct: -6.5,
        insufficient_sample: false,
        has_trades: true,
      },
      tech_only_stats: {
        total_trades: 40,
        win_trades: 20,
        loss_trades: 20,
        win_rate: 0.5,
        win_rate_pct: 50.0,
        avg_return: 0.012,
        avg_return_pct: 1.2,
        expected_value: 0.005,
        expected_value_pct: 0.5,
        avg_holding_days: 9.0,
        max_drawdown: -0.09,
        max_drawdown_pct: -9.0,
        insufficient_sample: false,
        has_trades: true,
      },
      three_layer_trades: [],
      tech_only_trades: [],
    },
    {
      strategy_name: '帶量突破 20 日新高',
      status: '觀望',
      action: '觀望',
      technical_signal: false,
      entry_price: null,
      stop_loss: null,
      take_profit: null,
      max_holding_days: 20,
      trigger_condition: '突破 105.5 元且量能放大',
      can_backtest: true,
      backtest_message: null,
      three_layer_stats: {
        total_trades: 12,
        win_trades: 7,
        loss_trades: 5,
        win_rate: 0.583,
        win_rate_pct: 58.3,
        avg_return: 0.04,
        avg_return_pct: 4.0,
        expected_value: 0.018,
        expected_value_pct: 1.8,
        avg_holding_days: 7.0,
        max_drawdown: -0.05,
        max_drawdown_pct: -5.0,
        insufficient_sample: true, // Sample insufficient
        has_trades: true,
      },
      tech_only_stats: null,
      three_layer_trades: [],
      tech_only_trades: [],
    },
    {
      strategy_name: 'MACD 金叉',
      status: '觀望',
      action: '觀望',
      technical_signal: false,
      entry_price: null,
      stop_loss: null,
      take_profit: null,
      max_holding_days: 20,
      trigger_condition: 'DIF 向上突破 MACD',
      can_backtest: true,
      backtest_message: null,
      three_layer_stats: null,
      tech_only_stats: null,
      three_layer_trades: [],
      tech_only_trades: [],
    },
    {
      strategy_name: 'KD 低檔金叉',
      status: '觀望',
      action: '觀望',
      technical_signal: false,
      entry_price: null,
      stop_loss: null,
      take_profit: null,
      max_holding_days: 20,
      trigger_condition: 'K 值於 20 以下向上突破 D 值',
      can_backtest: true,
      backtest_message: null,
      three_layer_stats: null,
      tech_only_stats: null,
      three_layer_trades: [],
      tech_only_trades: [],
    },
  ]

  it('renders 1 entry strategy highlighted and 3 watching strategies with trigger conditions', () => {
    render(
      <StrategyTable
        strategies={mockStrategies}
        selectedStrategyName="均線拉回 20MA"
      />
    )

    // Check entry strategy row
    const entryRow = screen.getByTestId('strategy-row-均線拉回 20MA')
    expect(entryRow).toHaveTextContent('★ 進場')
    expect(entryRow).toHaveTextContent('進場：100')
    expect(entryRow).toHaveTextContent('停損：94')
    expect(entryRow).toHaveTextContent('停利：109')
    expect(entryRow).toHaveTextContent('64.0%')
    expect(entryRow).toHaveTextContent('(16/25 筆)')

    // Check watching strategy row with trigger condition
    const breakoutRow = screen.getByTestId('strategy-row-帶量突破 20 日新高')
    expect(breakoutRow).toHaveTextContent('觀望')
    expect(breakoutRow).toHaveTextContent('突破 105.5 元且量能放大')
    // Sample insufficient badge
    expect(breakoutRow).toHaveTextContent('樣本不足')

    // Check watching rows
    expect(screen.getByTestId('strategy-row-MACD 金叉')).toHaveTextContent('DIF 向上突破 MACD')
    expect(screen.getByTestId('strategy-row-KD 低檔金叉')).toHaveTextContent(
      'K 值於 20 以下向上突破 D 值'
    )
  })

  it('triggers onSelectStrategy when clicking a row', () => {
    const handleSelect = vi.fn()
    render(
      <StrategyTable
        strategies={mockStrategies}
        selectedStrategyName="均線拉回 20MA"
        onSelectStrategy={handleSelect}
      />
    )

    fireEvent.click(screen.getByTestId('strategy-row-MACD 金叉'))
    expect(handleSelect).toHaveBeenCalledWith('MACD 金叉')
  })

  it('expands equity curve card and renders chart on row click, collapses on second click', () => {
    const strategiesWithCurves: StrategyItem[] = [
      {
        ...mockStrategies[0],
        three_layer_stats: {
          ...mockStrategies[0].three_layer_stats!,
          equity_curve: [
            { date: '2024-01-02', equity: 1.0, drawdown: 0.0 },
            { date: '2024-01-10', equity: 1.08, drawdown: 0.0 },
            { date: '2024-01-20', equity: 1.15, drawdown: 0.0 },
          ],
        },
        tech_only_stats: {
          ...mockStrategies[0].tech_only_stats!,
          equity_curve: [
            { date: '2024-01-02', equity: 1.0, drawdown: 0.0 },
            { date: '2024-01-15', equity: 0.98, drawdown: 0.02 },
            { date: '2024-01-25', equity: 1.04, drawdown: 0.0 },
          ],
        },
      },
      mockStrategies[2], // MACD without trades
    ]

    render(<StrategyTable strategies={strategiesWithCurves} />)

    // Initially card should not be visible
    expect(screen.queryByTestId('equity-curve-card-均線拉回 20MA')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(screen.getByTestId('strategy-row-均線拉回 20MA'))

    // Now card is visible with chart and metrics
    expect(screen.getByTestId('equity-curve-card-均線拉回 20MA')).toBeInTheDocument()
    expect(screen.getByTestId('equity-curve-chart')).toBeInTheDocument()
    expect(screen.getByTestId('equity-curve-svg')).toBeInTheDocument()
    expect(screen.getByText(/三層檢驗風控回測/)).toBeInTheDocument()
    expect(screen.getByText(/純技術面回測/)).toBeInTheDocument()

    // Click again to collapse
    fireEvent.click(screen.getByTestId('strategy-row-均線拉回 20MA'))
    expect(screen.queryByTestId('equity-curve-card-均線拉回 20MA')).not.toBeInTheDocument()

    // Click MACD row without trades
    fireEvent.click(screen.getByTestId('strategy-row-MACD 金叉'))
    expect(screen.getByTestId('equity-curve-card-MACD 金叉')).toBeInTheDocument()
    expect(screen.getByTestId('no-equity-curve')).toHaveTextContent('歷史交易資料不足')
  })
})
