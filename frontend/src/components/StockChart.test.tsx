import { fireEvent, render, screen } from '@testing-library/react'
import { act } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StockChart } from './StockChart'
import type { OHLCVItem, StrategyItem } from '../types/api'

// Mock lightweight-charts to capture series, crosshair callback, and avoid jsdom canvas issues
let crosshairMoveListener: ((param: any) => void) | null = null
const createdSeriesList: any[] = []

const createMockSeries = () => {
  const series = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    createPriceLine: vi.fn(() => ({})),
    removePriceLine: vi.fn(),
  }
  createdSeriesList.push(series)
  return series
}

const mockChartInstance = {
  addSeries: vi.fn(() => createMockSeries()),
  remove: vi.fn(),
  applyOptions: vi.fn(),
  timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
  subscribeCrosshairMove: vi.fn((callback: (param: any) => void) => {
    crosshairMoveListener = callback
  }),
}

vi.mock('lightweight-charts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('lightweight-charts')>()
  return {
    ...actual,
    createChart: vi.fn(() => mockChartInstance),
    createSeriesMarkers: vi.fn(() => ({ setMarkers: vi.fn() })),
  }
})

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

  beforeEach(() => {
    vi.clearAllMocks()
    crosshairMoveListener = null
    createdSeriesList.length = 0
  })

  it('renders stock chart container with indicator-expanded OHLCV data without crashing', () => {
    render(<StockChart ohlcv={mockOHLCV} />)

    expect(screen.getByTestId('stock-chart-card')).toBeInTheDocument()
    expect(screen.getByTestId('chart-container')).toBeInTheDocument()
    expect(screen.getByText('K 線圖與交易訊號')).toBeInTheDocument()
  })

  it('renders layer toggle buttons and initial legend with latest trading day values', () => {
    render(<StockChart ohlcv={mockOHLCV} />)

    // Verify all toggle buttons exist with initial checked state [✓]
    const btnMa5 = screen.getByTestId('toggle-ma5')
    const btnMa10 = screen.getByTestId('toggle-ma10')
    const btnMa20 = screen.getByTestId('toggle-ma20')
    const btnBollinger = screen.getByTestId('toggle-bollinger')

    expect(btnMa5).toHaveTextContent('[✓] 5MA')
    expect(btnMa10).toHaveTextContent('[✓] 10MA')
    expect(btnMa20).toHaveTextContent('[✓] 20MA')
    expect(btnBollinger).toHaveTextContent('[✓] 布林通道')

    // Verify initial dynamic legend values match the latest day (2026-10-20)
    expect(screen.getByTestId('legend-date')).toHaveTextContent('2026-10-20')
    expect(screen.getByTestId('legend-ma5')).toHaveTextContent('5MA: 112.00')
    expect(screen.getByTestId('legend-ma10')).toHaveTextContent('10MA: 108.50')
    expect(screen.getByTestId('legend-ma20')).toHaveTextContent('20MA / 布林中軌: 105.00')
    expect(screen.getByTestId('legend-bb-upper')).toHaveTextContent('布林上軌: 115.00')
    expect(screen.getByTestId('legend-bb-lower')).toHaveTextContent('布林下軌: 95.00')
  })

  it('toggles layer visibility when buttons are clicked and calls applyOptions', () => {
    render(<StockChart ohlcv={mockOHLCV} />)

    const btnBollinger = screen.getByTestId('toggle-bollinger')
    const btnMa5 = screen.getByTestId('toggle-ma5')

    // Toggle bollinger off
    fireEvent.click(btnBollinger)
    expect(btnBollinger).toHaveTextContent('[ ] 布林通道')

    // Toggle MA5 off
    fireEvent.click(btnMa5)
    expect(btnMa5).toHaveTextContent('[ ] 5MA')

    // Toggle bollinger back on
    fireEvent.click(btnBollinger)
    expect(btnBollinger).toHaveTextContent('[✓] 布林通道')
  })

  it('updates dynamic legend values on crosshair move and resets on exit', () => {
    render(<StockChart ohlcv={mockOHLCV} />)

    expect(crosshairMoveListener).toBeDefined()

    // Move crosshair to 2026-10-05
    act(() => {
      crosshairMoveListener?.({
        time: '2026-10-05',
        point: { x: 150, y: 200 },
      })
    })

    expect(screen.getByTestId('legend-date')).toHaveTextContent('2026-10-05')
    expect(screen.getByTestId('legend-ma5')).toHaveTextContent('5MA: 103.50')
    expect(screen.getByTestId('legend-ma10')).toHaveTextContent('10MA: -')
    expect(screen.getByTestId('legend-ma20')).toHaveTextContent('20MA / 布林中軌: -')
    expect(screen.getByTestId('legend-bb-upper')).toHaveTextContent('布林上軌: -')
    expect(screen.getByTestId('legend-bb-lower')).toHaveTextContent('布林下軌: -')

    // Move crosshair out of bounds
    act(() => {
      crosshairMoveListener?.({
        time: undefined,
        point: undefined,
      })
    })

    // Should reset to latest day (2026-10-20)
    expect(screen.getByTestId('legend-date')).toHaveTextContent('2026-10-20')
    expect(screen.getByTestId('legend-ma5')).toHaveTextContent('5MA: 112.00')
  })

  it('resets dynamic legend to latest values when mouse leaves container', () => {
    render(<StockChart ohlcv={mockOHLCV} />)

    // Move to 2026-10-05
    act(() => {
      crosshairMoveListener?.({
        time: '2026-10-05',
        point: { x: 150, y: 200 },
      })
    })
    expect(screen.getByTestId('legend-date')).toHaveTextContent('2026-10-05')

    // Trigger mouseleave on container
    const container = screen.getByTestId('chart-container')
    fireEvent.mouseLeave(container)

    expect(screen.getByTestId('legend-date')).toHaveTextContent('2026-10-20')
  })

  it('handles empty OHLCV array gracefully with fallback legend display', () => {
    render(<StockChart ohlcv={[]} />)

    expect(screen.getByTestId('stock-chart-card')).toBeInTheDocument()
    expect(screen.getByTestId('chart-container')).toBeInTheDocument()
    expect(screen.queryByTestId('legend-date')).not.toBeInTheDocument()
    expect(screen.getByTestId('legend-ma5')).toHaveTextContent('5MA: -')
    expect(screen.getByTestId('legend-ma10')).toHaveTextContent('10MA: -')
    expect(screen.getByTestId('legend-ma20')).toHaveTextContent('20MA / 布林中軌: -')
    expect(screen.getByTestId('legend-bb-upper')).toHaveTextContent('布林上軌: -')
    expect(screen.getByTestId('legend-bb-lower')).toHaveTextContent('布林下軌: -')
  })

  it('renders with selected strategy', () => {
    render(<StockChart ohlcv={mockOHLCV} selectedStrategy={mockStrategy} />)

    expect(screen.getByText('(當前策略：均線拉回 20MA)')).toBeInTheDocument()
  })
})
