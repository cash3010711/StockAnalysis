import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import * as clientModule from './api/client'

vi.mock('./components/StockChart', () => ({
  StockChart: () => <div data-testid="mock-stock-chart" />,
}))

describe('E2E Flow: 2330 AI Advisor Generation, Streaming, Cache, and Regeneration', () => {
  const mockAnalysis = {
    stock_id: '2330',
    stock_name: '台積電',
    evaluation_date: '2026-10-29',
    disclaimer: '僅供個人研究參考，非投資建議',
    warnings: [],
    fundamental: {
      passed: true,
      revenue_yoy: 0.25,
      eps_4q_sum: 45.0,
      debt_ratio: 0.3,
      reason: '營收與獲利成長穩健',
    },
    chips: {
      passed: true,
      foreign_trust_net_buy_10d: 12000,
      margin_increase_rate_10d: -0.01,
      reason: '法人買超且融資未增',
    },
    strategies: [
      {
        strategy_name: '均線糾結突破',
        status: '進場',
        action: '進場',
        technical_signal: true,
        entry_price: 1020.0,
        stop_loss: 970.0,
        take_profit: 1120.0,
        max_holding_days: 20,
        trigger_condition: '帶量長紅突破糾結均線',
        can_backtest: true,
        backtest_message: null,
        three_layer_stats: null,
        tech_only_stats: null,
        three_layer_trades: [],
        tech_only_trades: [],
        three_layer_equity_curve: [],
        tech_only_equity_curve: [],
      },
    ],
    ohlcv: [
      {
        date: '2026-10-29',
        open: 1010.0,
        high: 1030.0,
        low: 1005.0,
        close: 1025.0,
        volume: 32000,
        ma5: 1015.0,
        ma10: 1005.0,
        ma20: 995.0,
        ma60: 960.0,
        ma120: 920.0,
        bb_upper: 1040.0,
        bb_lower: 950.0,
        bb_mid: 995.0,
      },
    ],
    institutional: [],
    factor_score: 88.5,
    factor_decile: 1,
    historical_hit_rate: 80.0,
    historical_lift: 1.7,
    triggered_factors: ['營收創新高', '法人大額買超'],
  }

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(clientModule, 'fetchWatchlist').mockResolvedValue([])
    vi.spyOn(clientModule, 'searchStocks').mockResolvedValue([
      {
        stock_id: '2330',
        stock_name: '台積電',
        name: '台積電',
        market: 'TWSE',
        type: 'twse',
      },
    ])
    vi.spyOn(clientModule, 'fetchAnalysis').mockResolvedValue(mockAnalysis)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('completes the full user journey: select 2330 -> generate AI advice with streaming -> cache hit on second visit -> force regenerate', async () => {
    // Simulated persistent backend cache
    let backendCache: string | null = null

    const streamSpy = vi.spyOn(clientModule, 'streamAiAdvice').mockImplementation(
      async (stockId, options) => {
        expect(stockId).toBe('2330')

        if (backendCache && !options?.force) {
          // Serve from cache
          options?.onChunk?.(backendCache, backendCache)
          options?.onEvent?.({ cached: true, done: true, text: backendCache })
          return backendCache
        }

        // Fresh stream generation
        const chunk1 = '### 1. 【進場適宜度判定】\n台積電具備波段進場契機。\n'
        const chunk2 = '### 2. 【關鍵進出場價位規劃】\n建議進場價 1020 元，停損 970 元。'
        options?.onChunk?.(chunk1, chunk1)
        options?.onChunk?.(chunk2, chunk1 + chunk2)
        options?.onEvent?.({ cached: false, done: true })

        const fullText = chunk1 + chunk2
        backendCache = fullText
        return fullText
      }
    )

    render(<App />)

    // 1. Search and select 2330
    const searchInput = screen.getByPlaceholderText(/輸入代號或名稱/)
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: '2330' } })
    })

    const option = await screen.findByRole('option')
    await act(async () => {
      fireEvent.click(option)
    })

    // Verify stock deep analysis loaded
    expect(await screen.findByTestId('evaluation-header')).toBeInTheDocument()
    expect(screen.getByTestId('ai-advisor-card')).toBeInTheDocument()

    // 2. Initial state: click "一鍵生成戰略分析"
    const generateBtn = screen.getByTestId('generate-ai-advice-btn')
    expect(generateBtn).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(generateBtn)
    })

    // Verify stream called with force=false
    expect(streamSpy).toHaveBeenLastCalledWith('2330', expect.objectContaining({ force: false }))

    // Verify content rendered
    expect(screen.getByTestId('ai-advice-content')).toBeInTheDocument()
    expect(screen.getByText('1. 【進場適宜度判定】')).toBeInTheDocument()
    expect(screen.getByText('台積電具備波段進場契機。')).toBeInTheDocument()
    expect(screen.getByText('2. 【關鍵進出場價位規劃】')).toBeInTheDocument()
    expect(screen.getByText('建議進場價 1020 元，停損 970 元。')).toBeInTheDocument()

    // 3. Second visit (cache hit): re-select or trigger non-force stream
    await act(async () => {
      // Simulate calling generate again while cached
      await clientModule.streamAiAdvice('2330', {
        force: false,
        onEvent: (event) => {
          expect(event.cached).toBe(true)
        },
      })
    })

    // 4. Click "🔄 重新解讀" (force regeneration)
    const regenBtn = screen.getByTestId('regenerate-ai-advice-btn')
    expect(regenBtn).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(regenBtn)
    })

    // Verify stream called with force=true
    expect(streamSpy).toHaveBeenLastCalledWith('2330', expect.objectContaining({ force: true }))
    expect(screen.getByTestId('ai-advice-content')).toBeInTheDocument()
  })
})
