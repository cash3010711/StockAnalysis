import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistView } from './WatchlistView'
import type { WatchlistItem } from '../types/api'

describe('WatchlistView Component', () => {
  const mockWatchlist: WatchlistItem[] = [
    {
      stock_id: '2330',
      stock_name: '台積電',
      added_date: '2026-10-15',
      added_price: 950.0,
      current_price: 980.0,
      current_date: '2026-10-27',
      change_pct: 3.16,
      return_pct: 3.16,
      notes: '波段核心標的',
    },
    {
      stock_id: '2454',
      stock_name: '聯發科',
      added_date: '2026-10-18',
      added_price: 1250.0,
      current_price: 1200.0,
      current_date: '2026-10-27',
      change_pct: -4.0,
      return_pct: -4.0,
      notes: '',
    },
  ]

  it('renders empty message when watchlist is empty', () => {
    const handleSelect = vi.fn()
    const handleRemove = vi.fn()

    render(
      <WatchlistView
        watchlist={[]}
        onSelectStock={handleSelect}
        onRemove={handleRemove}
      />
    )

    expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument()
    expect(screen.getByText('尚未加入任何自選股')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist-count-badge')).toHaveTextContent('追蹤中：0 檔')
  })

  it('renders watchlist table with stock details and return rates', () => {
    const handleSelect = vi.fn()
    const handleRemove = vi.fn()

    render(
      <WatchlistView
        watchlist={mockWatchlist}
        onSelectStock={handleSelect}
        onRemove={handleRemove}
      />
    )

    expect(screen.getByTestId('watchlist-count-badge')).toHaveTextContent('追蹤中：2 檔')
    expect(screen.getByTestId('watchlist-table')).toBeInTheDocument()

    // Row 1 (2330)
    const row2330 = screen.getByTestId('watchlist-row-2330')
    expect(row2330).toHaveTextContent('2330')
    expect(row2330).toHaveTextContent('台積電')
    expect(row2330).toHaveTextContent('2026-10-15')
    expect(row2330).toHaveTextContent('950.00')
    expect(row2330).toHaveTextContent('980.00')
    expect(row2330).toHaveTextContent('+3.16%')
    expect(row2330).toHaveTextContent('波段核心標的')

    // Row 2 (2454)
    const row2454 = screen.getByTestId('watchlist-row-2454')
    expect(row2454).toHaveTextContent('2454')
    expect(row2454).toHaveTextContent('聯發科')
    expect(row2454).toHaveTextContent('1250.00')
    expect(row2454).toHaveTextContent('1200.00')
    expect(row2454).toHaveTextContent('-4.00%')
  })

  it('triggers onSelectStock when clicking stock name or analyze button', () => {
    const handleSelect = vi.fn()
    const handleRemove = vi.fn()

    render(
      <WatchlistView
        watchlist={mockWatchlist}
        onSelectStock={handleSelect}
        onRemove={handleRemove}
      />
    )

    // Click stock name
    fireEvent.click(screen.getByTestId('btn-select-2330'))
    expect(handleSelect).toHaveBeenCalledWith('2330')

    // Click analyze button
    fireEvent.click(screen.getByTestId('btn-analyze-2454'))
    expect(handleSelect).toHaveBeenCalledWith('2454')
  })

  it('triggers onRemove when clicking remove button', () => {
    const handleSelect = vi.fn()
    const handleRemove = vi.fn()

    render(
      <WatchlistView
        watchlist={mockWatchlist}
        onSelectStock={handleSelect}
        onRemove={handleRemove}
      />
    )

    fireEvent.click(screen.getByTestId('btn-remove-2330'))
    expect(handleRemove).toHaveBeenCalledWith('2330')
  })

  it('renders error message when error prop is provided', () => {
    render(
      <WatchlistView
        watchlist={[]}
        error="載入自選股失敗"
        onSelectStock={vi.fn()}
        onRemove={vi.fn()}
      />
    )

    expect(screen.getByTestId('watchlist-error')).toHaveTextContent('載入自選股失敗')
  })
})
