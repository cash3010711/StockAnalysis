import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SearchBox } from './SearchBox'

describe('SearchBox component', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('debounces user input and shows candidate list, clicking triggers onSelectStock', async () => {
    const mockStocks = [
      {
        stock_id: '2330',
        stock_name: '台積電',
        name: '台積電',
        market: 'TWSE',
        type: 'twse',
        industry_category: '半導體業',
      },
      {
        stock_id: '2337',
        stock_name: '旺宏',
        name: '旺宏',
        market: 'TWSE',
        type: 'twse',
        industry_category: '半導體業',
      },
    ]

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockStocks,
    } as Response)

    const handleSelect = vi.fn()
    render(<SearchBox onSelectStock={handleSelect} />)

    const input = screen.getByLabelText('股票搜尋')
    fireEvent.change(input, { target: { value: '233' } })

    // Before debounce 250ms, fetch shouldn't be called
    expect(fetchSpy).not.toHaveBeenCalled()

    // Advance timers by 250ms to fire the debounced effect
    await act(async () => {
      vi.advanceTimersByTime(250)
    })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/stocks?q=233',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    )

    // Check candidate options
    expect(screen.getByText('台積電')).toBeInTheDocument()
    expect(screen.getByText('旺宏')).toBeInTheDocument()

    // Click candidate
    fireEvent.click(screen.getByText('台積電'))
    expect(handleSelect).toHaveBeenCalledWith('2330', '台積電')
  })

  it('shows "查無符合股票" when candidate list is empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response)

    const handleSelect = vi.fn()
    render(<SearchBox onSelectStock={handleSelect} />)

    const input = screen.getByLabelText('股票搜尋')
    fireEvent.change(input, { target: { value: '9999' } })

    await act(async () => {
      vi.advanceTimersByTime(250)
    })

    expect(screen.getByText('查無符合股票')).toBeInTheDocument()
  })
})
