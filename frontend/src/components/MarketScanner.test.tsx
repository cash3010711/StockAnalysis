import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MarketScanner } from './MarketScanner'
import type { ScannerOptionsResponse, ScanMatchedStock } from '../types/api'

const mockOptions: ScannerOptionsResponse = {
  pools: [
    { id: 'cached', name: '本機已快取股票' },
    { id: 'tw50', name: '熱門權值／台灣 50 代表股' },
    { id: 'all', name: '全市場上市櫃普通股' },
  ],
  industries: ['半導體業', '電腦及周邊設備業', '金融保險業'],
  strategies: [
    '均線多頭排列',
    '均線拉回 20MA',
    '帶量突破 20 日新高',
    'KD 低檔金叉',
    'MACD 柱狀圖翻紅',
  ],
  cached_count: 15,
  defaults: {
    pool: 'cached',
    industry_category: null,
    sync_latest: false,
    require_fundamental: true,
    require_chips: true,
    strategies: [
      '均線多頭排列',
      '均線拉回 20MA',
      '帶量突破 20 日新高',
      'KD 低檔金叉',
      'MACD 柱狀圖翻紅',
    ],
  },
}

const mockMatchedStock1: ScanMatchedStock = {
  stock_id: '2330',
  stock_name: '台積電',
  market: '上市',
  type: 'twse',
  industry_category: '半導體業',
  close: 980.0,
  evaluation_date: '2026-10-21',
  triggered_strategies: ['均線拉回 20MA'],
  entry_price: 980.0,
  stop_loss: 920.0,
  take_profit: 1070.0,
  max_holding_days: 20,
  fundamental_passed: true,
  revenue_yoy: 0.25,
  eps_4q_sum: 42.5,
  debt_ratio: 0.32,
  fundamental_reason: '基本面各項條件全數合格',
  chips_passed: true,
  foreign_trust_net_buy_10d: 8500,
  margin_increase_rate_10d: 0.05,
  chips_reason: '籌碼面各項條件全數合格',
  best_strategy_name: '均線拉回 20MA',
  best_win_rate_pct: 66.7,
  best_avg_return_pct: 4.8,
  strategy_stats: [
    {
      strategy_name: '均線拉回 20MA',
      can_backtest: true,
      three_layer_win_rate_pct: 66.7,
      three_layer_avg_return_pct: 4.8,
    },
  ],
}

const mockMatchedStock2: ScanMatchedStock = {
  stock_id: '2454',
  stock_name: '聯發科',
  market: '上市',
  type: 'twse',
  industry_category: '半導體業',
  close: 1250.0,
  evaluation_date: '2026-10-21',
  triggered_strategies: ['帶量突破 20 日新高'],
  entry_price: 1250.0,
  stop_loss: 1180.0,
  take_profit: 1380.0,
  max_holding_days: 20,
  fundamental_passed: true,
  revenue_yoy: 0.15,
  eps_4q_sum: 55.0,
  debt_ratio: 0.28,
  fundamental_reason: '基本面各項條件全數合格',
  chips_passed: true,
  foreign_trust_net_buy_10d: 3200,
  margin_increase_rate_10d: 0.02,
  chips_reason: '籌碼面各項條件全數合格',
  best_strategy_name: '帶量突破 20 日新高',
  best_win_rate_pct: 75.0,
  best_avg_return_pct: 8.2,
  strategy_stats: [
    {
      strategy_name: '帶量突破 20 日新高',
      can_backtest: true,
      three_layer_win_rate_pct: 75.0,
      three_layer_avg_return_pct: 8.2,
    },
  ],
}

function createNDJSONResponse(events: any[]) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      for (const ev of events) {
        controller.enqueue(encoder.encode(JSON.stringify(ev) + '\n'))
      }
      controller.close()
    },
  })

  return {
    ok: true,
    status: 200,
    body: stream,
  } as unknown as Response
}

describe('MarketScanner Component', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads options on mount and displays filter controls', async () => {
    render(<MarketScanner onSelectStock={vi.fn()} />)

    expect(screen.getByTestId('market-scanner')).toBeInTheDocument()
    expect(screen.getByText('全市場選股條件設定')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument()
    })

    const poolSelect = screen.getByTestId('pool-select') as HTMLSelectElement
    expect(poolSelect.value).toBe('cached')

    const industrySelect = screen.getByTestId('industry-select') as HTMLSelectElement
    expect(industrySelect.value).toBe('')

    const syncCheckbox = screen.getByTestId('sync-latest-checkbox') as HTMLInputElement
    expect(syncCheckbox.checked).toBe(false)

    const fundCheckbox = screen.getByTestId(
      'require-fundamental-checkbox'
    ) as HTMLInputElement
    expect(fundCheckbox.checked).toBe(true)

    const chipsCheckbox = screen.getByTestId(
      'require-chips-checkbox'
    ) as HTMLInputElement
    expect(chipsCheckbox.checked).toBe(true)
  })

  it('allows changing filters and strategy selection', async () => {
    render(<MarketScanner onSelectStock={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByTestId('strategy-checkbox-均線多頭排列')).toBeInTheDocument()
    })

    // Change pool
    const poolSelect = screen.getByTestId('pool-select')
    fireEvent.change(poolSelect, { target: { value: 'tw50' } })
    expect((poolSelect as HTMLSelectElement).value).toBe('tw50')

    // Change industry
    const industrySelect = screen.getByTestId('industry-select')
    fireEvent.change(industrySelect, { target: { value: 'tech' } })
    expect((industrySelect as HTMLSelectElement).value).toBe('tech')

    // Toggle sync checkbox
    const syncCheckbox = screen.getByTestId('sync-latest-checkbox')
    fireEvent.click(syncCheckbox)
    expect((syncCheckbox as HTMLInputElement).checked).toBe(true)

    // Uncheck and check strategies
    const stratCheckbox = screen.getByTestId('strategy-checkbox-均線多頭排列')
    fireEvent.click(stratCheckbox)
    expect((stratCheckbox as HTMLInputElement).checked).toBe(false)

    // Deselect all
    const deselectBtn = screen.getByText('取消全選')
    fireEvent.click(deselectBtn)
    expect(screen.getByText('⚠️ 請至少勾選一項技術策略以啟動篩選')).toBeInTheDocument()
    expect(screen.getByTestId('start-scan-btn')).toBeDisabled()

    // Select all
    const selectAllBtn = screen.getByText('全選')
    fireEvent.click(selectAllBtn)
    expect(screen.getByTestId('start-scan-btn')).not.toBeDisabled()
  })

  it('runs streaming scan, displays progress and matched stocks in table, and triggers onSelectStock', async () => {
    const onSelectStock = vi.fn()

    const events = [
      { event: 'start', total: 2 },
      {
        event: 'match',
        data: mockMatchedStock1,
        current: 1,
        total: 2,
        matched_count: 1,
      },
      {
        event: 'progress',
        current: 1,
        total: 2,
        stock_id: '2330',
        stock_name: '台積電',
        matched_count: 1,
        quota_exceeded: false,
      },
      {
        event: 'match',
        data: mockMatchedStock2,
        current: 2,
        total: 2,
        matched_count: 2,
      },
      {
        event: 'progress',
        current: 2,
        total: 2,
        stock_id: '2454',
        stock_name: '聯發科',
        matched_count: 2,
        quota_exceeded: false,
      },
      {
        event: 'done',
        total: 2,
        scanned: 2,
        matched_count: 2,
        quota_exceeded: false,
        warnings: [],
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/stream')) {
        return createNDJSONResponse(events)
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={onSelectStock} />)

    await waitFor(() => {
      expect(screen.getByTestId('start-scan-btn')).not.toBeDisabled()
    })

    const startBtn = screen.getByTestId('start-scan-btn')
    await act(async () => {
      fireEvent.click(startBtn)
    })

    // Progress information
    await waitFor(() => {
      expect(screen.getByTestId('scan-status-info')).toBeInTheDocument()
      expect(screen.getByText('符合條件：2 檔')).toBeInTheDocument()
    })

    // Table should contain both stocks
    expect(screen.getByTestId('stock-row-2330')).toBeInTheDocument()
    expect(screen.getByTestId('stock-row-2454')).toBeInTheDocument()
    expect(screen.getByText('2330 台積電')).toBeInTheDocument()
    expect(screen.getByText('2454 聯發科')).toBeInTheDocument()

    // Click stock to view deep analysis
    const stockBtn = screen.getByText('2330 台積電')
    fireEvent.click(stockBtn)
    expect(onSelectStock).toHaveBeenCalledWith('2330')

    // Click button "深度分析" on 2454
    const row2454 = screen.getByTestId('stock-row-2454')
    const deepAnalysisBtn = within(row2454).getByText('深度分析')
    fireEvent.click(deepAnalysisBtn)
    expect(onSelectStock).toHaveBeenCalledWith('2454')
  })

  it('supports sorting by different columns', async () => {
    const events = [
      { event: 'start', total: 2 },
      {
        event: 'match',
        data: mockMatchedStock1, // 2330: winRate 66.7, close 980
        current: 1,
        total: 2,
        matched_count: 1,
      },
      {
        event: 'match',
        data: mockMatchedStock2, // 2454: winRate 75.0, close 1250
        current: 2,
        total: 2,
        matched_count: 2,
      },
      {
        event: 'done',
        total: 2,
        scanned: 2,
        matched_count: 2,
        quota_exceeded: false,
        warnings: [],
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/stream')) {
        return createNDJSONResponse(events)
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByTestId('start-scan-btn')).not.toBeDisabled()
    })

    await act(async () => {
      fireEvent.click(screen.getByTestId('start-scan-btn'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('scanner-results-table')).toBeInTheDocument()
    })

    const rows = screen.getAllByRole('row')
    // Header is row 0. First data row should be 2454 because default sort is best_win_rate_pct desc (75.0 > 66.7)
    expect(rows[1]).toHaveTextContent('2454 聯發科')
    expect(rows[2]).toHaveTextContent('2330 台積電')

    // Click win rate sort to invert to asc (2330 first)
    fireEvent.click(screen.getByTestId('sort-best_win_rate_pct'))
    const rowsAfterSort = screen.getAllByRole('row')
    expect(rowsAfterSort[1]).toHaveTextContent('2330 台積電')
    expect(rowsAfterSort[2]).toHaveTextContent('2454 聯發科')

    // Sort by close price desc
    fireEvent.click(screen.getByTestId('sort-close'))
    const rowsByClose = screen.getAllByRole('row')
    expect(rowsByClose[1]).toHaveTextContent('2454 聯發科') // 1250 > 980
    expect(rowsByClose[2]).toHaveTextContent('2330 台積電')
  })

  it('displays quota exceeded warning banner when quota limit is hit', async () => {
    const events = [
      { event: 'start', total: 1 },
      {
        event: 'match',
        data: mockMatchedStock1,
        current: 1,
        total: 1,
        matched_count: 1,
      },
      {
        event: 'progress',
        current: 1,
        total: 1,
        stock_id: '2330',
        stock_name: '台積電',
        matched_count: 1,
        quota_exceeded: true,
      },
      {
        event: 'done',
        total: 1,
        scanned: 1,
        matched_count: 1,
        quota_exceeded: true,
        warnings: ['FinMind API 請求額度已達上限，後續標的已自動降級為本機快取模式'],
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/stream')) {
        return createNDJSONResponse(events)
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByTestId('start-scan-btn')).not.toBeDisabled()
    })

    await act(async () => {
      fireEvent.click(screen.getByTestId('start-scan-btn'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('quota-exceeded-alert')).toBeInTheDocument()
      expect(screen.getByText(/FinMind API 請求額度已達上限/)).toBeInTheDocument()
    })
  })

  it('supports aborting an in-progress scan and preserves matches', async () => {
    const stream = new ReadableStream({
      start(c) {
        const encoder = new TextEncoder()
        c.enqueue(
          encoder.encode(
            JSON.stringify({ event: 'start', total: 10 }) +
              '\n' +
              JSON.stringify({
                event: 'match',
                data: mockMatchedStock1,
                current: 1,
                total: 10,
                matched_count: 1,
              }) +
              '\n' +
              JSON.stringify({
                event: 'progress',
                current: 1,
                total: 10,
                stock_id: '2330',
                stock_name: '台積電',
                matched_count: 1,
                quota_exceeded: false,
              }) +
              '\n'
          )
        )
      },
    })

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/stream')) {
        return {
          ok: true,
          status: 200,
          body: stream,
        } as unknown as Response
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByTestId('start-scan-btn')).not.toBeDisabled()
    })

    await act(async () => {
      fireEvent.click(screen.getByTestId('start-scan-btn'))
    })

    // Now scan is running and abort button should appear
    await waitFor(() => {
      expect(screen.getByTestId('abort-scan-btn')).toBeInTheDocument()
    })

    // Click abort button
    await act(async () => {
      fireEvent.click(screen.getByTestId('abort-scan-btn'))
    })

    // Abort status message should be shown and matched stock preserved
    await waitFor(() => {
      expect(screen.getByText(/已手動中止掃描/)).toBeInTheDocument()
      expect(screen.getByTestId('stock-row-2330')).toBeInTheDocument()
    })
  })

  it('renders nightly action plan card with items and handles stock selection', async () => {
    const onSelectStock = vi.fn()
    const mockNightlyPlan = {
      found: true,
      plan_id: 'plan_20261026_183000',
      scan_date: '2026-10-26',
      created_at: '2026-10-26T18:30:00Z',
      status: 'completed',
      total_candidates: 45,
      selected_count: 1,
      items: [
        {
          item_id: 1,
          plan_id: 'plan_20261026_183000',
          stock_id: '2330',
          stock_name: '台積電',
          market: '上市',
          strategy: '均線拉回 20MA',
          win_rate: 0.725,
          trade_count: 15,
          entry_price: 1000.0,
          stop_loss: 950.0,
          take_profit: 1080.0,
          holding_days: 20,
          risk_reward_ratio: 1.6,
          close_price: 1000.0,
          volume: 25000000,
        },
      ],
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/nightly-plan')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockNightlyPlan,
        } as Response
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={onSelectStock} />)

    // Verify Nightly Plan Card appears
    expect(screen.getByTestId('nightly-plan-card')).toBeInTheDocument()
    expect(screen.getByText('🌙 隔日交易備戰清單')).toBeInTheDocument()

    // Verify loaded plan item details
    await waitFor(() => {
      expect(screen.getByTestId('nightly-plan-table')).toBeInTheDocument()
      expect(screen.getByText(/2330 台積電/)).toBeInTheDocument()
      expect(screen.getByText('72.5%')).toBeInTheDocument()
      expect(screen.getAllByText('1000.00').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('950.00')).toBeInTheDocument()
      expect(screen.getByText('1080.00')).toBeInTheDocument()
      expect(screen.getByText('1.6:1')).toBeInTheDocument()
    })

    // Click "查看 K 線" button
    const kLineBtn = screen.getByText('查看 K 線')
    fireEvent.click(kLineBtn)
    expect(onSelectStock).toHaveBeenCalledWith('2330')
  })

  it('triggers manual nightly plan scan on button click', async () => {
    let triggered = false
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/nightly-plan/trigger')) {
        triggered = true
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: 'completed', plan_id: 'p_new', selected_count: 0 }),
        } as Response
      }
      if (urlStr.includes('/api/scanner/nightly-plan')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            found: triggered,
            items: [],
            scan_date: '2026-10-26',
          }),
        } as Response
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={vi.fn()} />)

    const triggerBtn = screen.getByTestId('trigger-nightly-plan-btn')
    expect(triggerBtn).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(triggerBtn)
    })

    expect(triggered).toBe(true)
    await waitFor(() => {
      expect(screen.getByText(/隔日作戰清單已重新計算並完成更新/)).toBeInTheDocument()
    })
  })

  it('correctly passes industry filter options (tech / non_tech) to scan stream request', async () => {
    let capturedBody: any = null
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/stream')) {
        if (init && init.body) {
          capturedBody = JSON.parse(init.body as string)
        }
        return createNDJSONResponse([
          { event: 'start', total: 0 },
          {
            event: 'done',
            total: 0,
            scanned: 0,
            matched_count: 0,
            quota_exceeded: false,
            warnings: [],
          },
        ])
      }
      return { ok: false, status: 404 } as Response
    })

    render(<MarketScanner onSelectStock={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByTestId('industry-select')).toBeInTheDocument()
    })

    const industrySelect = screen.getByTestId('industry-select')
    expect(screen.getByText('科技股（電子八大類）')).toBeInTheDocument()
    expect(screen.getByText('非科技股')).toBeInTheDocument()

    // Test tech filter selection
    fireEvent.change(industrySelect, { target: { value: 'tech' } })
    expect((industrySelect as HTMLSelectElement).value).toBe('tech')

    const startBtn = screen.getByTestId('start-scan-btn')
    fireEvent.click(startBtn)

    await waitFor(() => {
      expect(capturedBody).not.toBeNull()
      expect(capturedBody.industry_category).toBe('tech')
    })
  })

  it('renders watchlist star buttons and toggles watchlist in scan results and nightly plan', async () => {
    const onToggleWatchlist = vi.fn()
    const mockWatchlist = [
      {
        stock_id: '2330',
        stock_name: '台積電',
        added_date: '2026-10-20',
        added_price: 950.0,
      },
    ]

    const mockNightlyPlan = {
      found: true,
      plan_id: 'plan_20261026_183000',
      scan_date: '2026-10-26',
      created_at: '2026-10-26T18:30:00Z',
      status: 'completed',
      total_candidates: 45,
      selected_count: 1,
      items: [
        {
          item_id: 1,
          plan_id: 'plan_20261026_183000',
          stock_id: '2330',
          stock_name: '台積電',
          market: '上市',
          strategy: '均線拉回 20MA',
          win_rate: 0.725,
          trade_count: 15,
          entry_price: 1000.0,
          stop_loss: 950.0,
          take_profit: 1080.0,
          holding_days: 20,
          risk_reward_ratio: 1.6,
          close_price: 1000.0,
          volume: 25000000,
        },
      ],
    }

    const events = [
      { event: 'start', total: 2 },
      {
        event: 'match',
        data: mockMatchedStock1, // 2330
        current: 1,
        total: 2,
        matched_count: 1,
      },
      {
        event: 'match',
        data: mockMatchedStock2, // 2454
        current: 2,
        total: 2,
        matched_count: 2,
      },
      {
        event: 'done',
        total: 2,
        scanned: 2,
        matched_count: 2,
        quota_exceeded: false,
        warnings: [],
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const urlStr = String(url)
      if (urlStr.includes('/api/scanner/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockOptions,
        } as Response
      }
      if (urlStr.includes('/api/scanner/nightly-plan')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockNightlyPlan,
        } as Response
      }
      if (urlStr.includes('/api/scanner/stream')) {
        return createNDJSONResponse(events)
      }
      return { ok: false, status: 404 } as Response
    })

    render(
      <MarketScanner
        onSelectStock={vi.fn()}
        watchlist={mockWatchlist}
        onToggleWatchlist={onToggleWatchlist}
      />
    )

    // Verify Nightly plan star button for 2330 (in watchlist -> ⭐)
    await waitFor(() => {
      const nightlyStar = screen.getByTestId('toggle-watchlist-nightly-2330')
      expect(nightlyStar).toBeInTheDocument()
      expect(nightlyStar).toHaveTextContent('⭐')
    })

    // Click nightly plan star button
    const nightlyStar = screen.getByTestId('toggle-watchlist-nightly-2330')
    fireEvent.click(nightlyStar)
    expect(onToggleWatchlist).toHaveBeenCalledWith('2330', '台積電', 1000.0)

    // Start scan to get scan results
    const startBtn = screen.getByTestId('start-scan-btn')
    fireEvent.click(startBtn)

    await waitFor(() => {
      expect(screen.getByTestId('toggle-watchlist-scanner-2330')).toBeInTheDocument()
      expect(screen.getByTestId('toggle-watchlist-scanner-2454')).toBeInTheDocument()
    })

    // 2330 is in watchlist -> ⭐
    const scanStar2330 = screen.getByTestId('toggle-watchlist-scanner-2330')
    expect(scanStar2330).toHaveTextContent('⭐')

    // 2454 is NOT in watchlist -> ☆
    const scanStar2454 = screen.getByTestId('toggle-watchlist-scanner-2454')
    expect(scanStar2454).toHaveTextContent('☆')

    // Click 2454 star button to add
    fireEvent.click(scanStar2454)
    expect(onToggleWatchlist).toHaveBeenCalledWith('2454', '聯發科', 1250.0)
  })
})
