import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('App Component Integration', () => {
  const mockLookup = [
    {
      stock_id: '2330',
      stock_name: '台積電',
      name: '台積電',
      market: 'TWSE',
      type: 'twse',
    },
  ]

  const mockAnalysis = {
    stock_id: '2330',
    stock_name: '台積電',
    evaluation_date: '2026-10-21',
    disclaimer: '僅供個人研究參考，非投資建議',
    warnings: [],
    fundamental: {
      passed: true,
      revenue_yoy: 0.18,
      eps_4q_sum: 42.0,
      debt_ratio: 0.3,
      reason: '',
    },
    chips: {
      passed: true,
      foreign_trust_net_buy_10d: 5400,
      margin_increase_rate_10d: 0.02,
      reason: '',
    },
    strategies: [
      {
        strategy_name: '均線拉回 20MA',
        status: '進場',
        action: '進場',
        technical_signal: true,
        entry_price: 980.0,
        stop_loss: 920.0,
        take_profit: 1070.0,
        max_holding_days: 20,
        trigger_condition: null,
        can_backtest: true,
        backtest_message: null,
        three_layer_stats: {
          total_trades: 30,
          win_trades: 20,
          loss_trades: 10,
          win_rate: 0.667,
          win_rate_pct: 66.7,
          avg_return: 0.045,
          avg_return_pct: 4.5,
          expected_value: 0.025,
          expected_value_pct: 2.5,
          avg_holding_days: 9.0,
          max_drawdown: -0.05,
          max_drawdown_pct: -5.0,
          insufficient_sample: false,
          has_trades: true,
        },
        tech_only_stats: null,
        three_layer_trades: [
          {
            entry_date: '2026-05-10',
            entry_price: 900.0,
            exit_date: '2026-05-20',
            exit_price: 960.0,
            stop_loss: 850.0,
            take_profit: 960.0,
            holding_days: 8,
            gross_return: 0.066,
            net_return: 0.06,
            exit_reason: '停利',
            is_win: true,
          },
        ],
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
        trigger_condition: '收盤突破 1000 元',
        can_backtest: true,
        backtest_message: null,
        three_layer_stats: null,
        tech_only_stats: null,
        three_layer_trades: [],
        tech_only_trades: [],
      },
    ],
    ohlcv: [
      {
        date: '2026-10-20',
        open: 970,
        high: 985,
        low: 965,
        close: 980,
        volume: 25000,
        ma5: 975.0,
        ma10: 960.0,
        ma20: 940.0,
        bb_upper: 980.0,
        bb_lower: 900.0,
        bb_mid: 940.0,
      },
      {
        date: '2026-10-21',
        open: 982,
        high: 990,
        low: 975,
        close: 985,
        volume: 28000,
        ma5: 978.5,
        ma10: 965.2,
        ma20: 950.0,
        bb_upper: 995.0,
        bb_lower: 905.0,
        bb_mid: 950.0,
      },
    ],
  }

  const mockScannerOptions = {
    pools: [{ id: 'cached', name: '本機已快取股票' }],
    industries: ['半導體業'],
    strategies: ['均線拉回 20MA'],
    cached_count: 10,
    defaults: {
      pool: 'cached',
      industry_category: null,
      sync_latest: false,
      require_fundamental: true,
      require_chips: true,
      strategies: ['均線拉回 20MA'],
    },
  }

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('renders welcome box initially and updates with analysis results on selecting stock', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/watchlist')) {
        return {
          ok: true,
          json: async () => [],
        } as Response
      }
      if (urlStr.includes('/api/stocks')) {
        return {
          ok: true,
          json: async () => mockLookup,
        } as Response
      }
      if (urlStr.includes('/api/analysis/2330')) {
        return {
          ok: true,
          json: async () => mockAnalysis,
        } as Response
      }
      if (urlStr.includes('/api/watchlist')) {
        return {
          ok: true,
          json: async () => [],
        } as Response
      }
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          json: async () => mockScannerOptions,
        } as Response
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response
    })

    render(<App />)

    await act(async () => {
      await Promise.resolve()
    })

    // Initial welcome box
    expect(screen.getByTestId('welcome-box')).toBeInTheDocument()
    expect(screen.getByTestId('disclaimer')).toBeInTheDocument()

    // Type into SearchBox
    const input = screen.getByLabelText('股票搜尋')
    fireEvent.change(input, { target: { value: '2330' } })

    await act(async () => {
      vi.advanceTimersByTime(250)
    })

    // Click candidate
    const option = screen.getByText('台積電')
    await act(async () => {
      fireEvent.click(option)
    })

    // Check evaluation header
    expect(screen.getByTestId('evaluation-header')).toBeInTheDocument()
    expect(screen.getByText('2330 台積電')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist-toggle-btn')).toHaveTextContent('加自選')
    expect(screen.getByTestId('eval-date-text')).toHaveTextContent(
      '評估日：2026-10-21（收盤後資料）'
    )

    // Check strategy table
    expect(screen.getByTestId('strategy-table')).toBeInTheDocument()
    expect(screen.getByTestId('strategy-row-均線拉回 20MA')).toHaveTextContent('進場：980')

    // Switch strategy by clicking on 帶量突破 20 日新高
    const breakoutRow = screen.getByTestId('strategy-row-帶量突破 20 日新高')
    fireEvent.click(breakoutRow)
    expect(screen.getByText('(當前策略：帶量突破 20 日新高)')).toBeInTheDocument()

    // Verify indicator toolbar & legend in full app integration
    expect(screen.getByTestId('layer-controls')).toBeInTheDocument()
    expect(screen.getByTestId('chart-legend')).toBeInTheDocument()
    expect(screen.getByTestId('toggle-bollinger')).toHaveTextContent('[✓] 布林通道')
    expect(screen.getByTestId('legend-ma5')).toHaveTextContent('5MA: 978.50')
    expect(screen.getByTestId('legend-ma10')).toHaveTextContent('10MA: 965.20')
    expect(screen.getByTestId('legend-ma20')).toHaveTextContent('20MA / 布林中軌: 950.00')

    // Toggle bollinger off
    fireEvent.click(screen.getByTestId('toggle-bollinger'))
    expect(screen.getByTestId('toggle-bollinger')).toHaveTextContent('[ ] 布林通道')
  })

  it('switches between single stock tab and market scanner tab with keep-alive state', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/watchlist')) {
        return {
          ok: true,
          json: async () => [],
        } as Response
      }
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          json: async () => mockScannerOptions,
        } as Response
      }
      if (urlStr.includes('/api/analysis/2330')) {
        return {
          ok: true,
          json: async () => mockAnalysis,
        } as Response
      }
      return { ok: false, status: 404 } as Response
    })

    render(<App />)

    await act(async () => {
      await Promise.resolve()
    })

    const singleView = screen.getByTestId('single-stock-view')
    const scannerView = screen.getByTestId('market-scanner-view')
    const watchlistView = screen.getByTestId('watchlist-view')
    const tabWatchlist = screen.getByTestId('tab-watchlist')

    // Single view visible by default
    expect(singleView).toBeVisible()
    expect(scannerView).not.toBeVisible()

    // Switch to watchlist tab
    fireEvent.click(tabWatchlist)

    expect(singleView).not.toBeVisible()
    expect(scannerView).not.toBeVisible()
    expect(watchlistView).toBeVisible()
    expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument()

    // Switch to scanner tab
    const tabScanner = screen.getByTestId('tab-scanner')
    fireEvent.click(tabScanner)

    expect(singleView).not.toBeVisible()
    expect(scannerView).toBeVisible()
    expect(screen.getByText('全市場選股條件設定')).toBeInTheDocument()

    // Switch back to single stock tab
    const tabSingle = screen.getByTestId('tab-single')
    fireEvent.click(tabSingle)

    expect(singleView).toBeVisible()
    expect(scannerView).not.toBeVisible()

    // Switch to watchlist tab
    fireEvent.click(tabWatchlist)

    expect(singleView).not.toBeVisible()
    expect(scannerView).not.toBeVisible()
    expect(watchlistView).toBeVisible()
    expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument()
  })
})
