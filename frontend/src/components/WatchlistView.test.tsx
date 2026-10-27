import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistView } from './WatchlistView'
import type { WatchlistItem } from '../types/api'
import * as client from '../api/client'

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

  it('renders group tabs, filters stocks by group, and distinguishes between remove from group and complete delete', async () => {
    const mockGroups = [
      { id: 1, name: 'AI概念' },
      { id: 2, name: '高股息' },
    ]

    const watchlistWithGroups: WatchlistItem[] = [
      {
        stock_id: '2330',
        stock_name: '台積電',
        added_date: '2026-10-15',
        added_price: 950.0,
        current_price: 980.0,
        groups: [{ id: 1, name: 'AI概念' }],
        suggested_strategy: '均線拉回 20MA',
        entry_price: 980.0,
        stop_loss: 930.0,
        take_profit: 1060.0,
      },
      {
        stock_id: '2454',
        stock_name: '聯發科',
        added_date: '2026-10-18',
        added_price: 1250.0,
        current_price: 1200.0,
        groups: [{ id: 2, name: '高股息' }],
        suggested_strategy: '觀望',
        trigger_condition: '收盤突破 1300 元',
      },
    ]

    vi.spyOn(client, 'fetchWatchlistGroups').mockResolvedValue(mockGroups)
    const removeStockFromGroupSpy = vi.spyOn(client, 'removeStockFromGroup').mockResolvedValue({
      success: true,
      stock_id: '2330',
      group_id: 1,
      message: 'Removed',
    })
    const handleRemove = vi.fn()
    const handleRefresh = vi.fn()

    render(
      <WatchlistView
        watchlist={watchlistWithGroups}
        onSelectStock={vi.fn()}
        onRemove={handleRemove}
        onRefresh={handleRefresh}
      />
    )

    // Public pool tab shows both stocks
    await waitFor(() => {
      expect(screen.getByTestId('group-tab-1')).toHaveTextContent('AI概念 (1)')
      expect(screen.getByTestId('group-tab-2')).toHaveTextContent('高股息 (1)')
    })

    expect(screen.getByTestId('watchlist-row-2330')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist-row-2454')).toBeInTheDocument()

    // Public pool action button says "徹底刪除"
    const deleteBtn = screen.getByTestId('btn-remove-2330')
    expect(deleteBtn).toHaveTextContent('徹底刪除')
    fireEvent.click(deleteBtn)
    expect(handleRemove).toHaveBeenCalledWith('2330')

    // Switch to AI概念 tab
    fireEvent.click(screen.getByTestId('group-tab-1'))

    // AI概念 tab only contains 2330
    expect(screen.getByTestId('watchlist-row-2330')).toBeInTheDocument()
    expect(screen.queryByTestId('watchlist-row-2454')).not.toBeInTheDocument()

    // Action button now says "移出群組"
    const removeGroupBtn = screen.getByTestId('btn-remove-2330')
    expect(removeGroupBtn).toHaveTextContent('移出群組')

    fireEvent.click(removeGroupBtn)
    await waitFor(() => {
      expect(removeStockFromGroupSpy).toHaveBeenCalledWith('2330', 1)
      expect(handleRefresh).toHaveBeenCalled()
    })
  })

  it('creates a new group and manages stock groups via modal', async () => {
    const mockGroups = [{ id: 1, name: 'AI概念' }]
    vi.spyOn(client, 'fetchWatchlistGroups').mockResolvedValue(mockGroups)
    const createGroupSpy = vi.spyOn(client, 'createWatchlistGroup').mockResolvedValue({
      id: 2,
      name: '波段核心',
    })
    const updateStockGroupsSpy = vi.spyOn(client, 'updateStockGroups').mockResolvedValue({
      success: true,
      stock_id: '2330',
      group_ids: [1, 2],
    })
    const handleRefresh = vi.fn()

    const watchlistWithGroups: WatchlistItem[] = [
      {
        stock_id: '2330',
        stock_name: '台積電',
        added_date: '2026-10-15',
        added_price: 950.0,
        groups: [{ id: 1, name: 'AI概念' }],
      },
    ]

    render(
      <WatchlistView
        watchlist={watchlistWithGroups}
        onSelectStock={vi.fn()}
        onRemove={vi.fn()}
        onRefresh={handleRefresh}
      />
    )

    await waitFor(() => {
      expect(screen.getByTestId('group-tab-1')).toBeInTheDocument()
    })

    // Create a new group
    const input = screen.getByTestId('new-group-input')
    fireEvent.change(input, { target: { value: '波段核心' } })
    const createBtn = screen.getByTestId('create-group-btn')
    fireEvent.click(createBtn)

    await waitFor(() => {
      expect(createGroupSpy).toHaveBeenCalledWith('波段核心')
      expect(screen.getByTestId('group-tab-2')).toHaveTextContent('波段核心')
    })

    // Open manage groups modal for 2330
    const manageBtn = screen.getByTestId('btn-manage-groups-2330')
    fireEvent.click(manageBtn)

    expect(screen.getByTestId('manage-groups-modal')).toBeInTheDocument()
    const checkboxGroup2 = screen.getByTestId('modal-group-checkbox-2')
    expect(checkboxGroup2).not.toBeChecked()

    // Check group 2
    fireEvent.click(checkboxGroup2)
    expect(checkboxGroup2).toBeChecked()

    // Click save
    const saveBtn = screen.getByTestId('modal-save-btn')
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(updateStockGroupsSpy).toHaveBeenCalledWith('2330', [1, 2])
      expect(handleRefresh).toHaveBeenCalled()
    })
  })

  it('renders suggested strategy, entry/exit points and triggers manual sync', async () => {
    const syncWatchlistSpy = vi.spyOn(client, 'syncWatchlist').mockResolvedValue({
      success: true,
      synced_count: 2,
      total_count: 2,
      errors: [],
    })
    const handleRefresh = vi.fn()

    const watchlistWithStrategies: WatchlistItem[] = [
      {
        stock_id: '2330',
        stock_name: '台積電',
        added_date: '2026-10-15',
        added_price: 950.0,
        current_price: 980.0,
        suggested_strategy: '均線拉回 20MA',
        entry_price: 980.0,
        stop_loss: 930.0,
        take_profit: 1060.0,
      },
      {
        stock_id: '2454',
        stock_name: '聯發科',
        added_date: '2026-10-18',
        added_price: 1250.0,
        current_price: 1200.0,
        suggested_strategy: '觀望',
        trigger_condition: '收盤突破 1300 元',
      },
    ]

    render(
      <WatchlistView
        watchlist={watchlistWithStrategies}
        onSelectStock={vi.fn()}
        onRemove={vi.fn()}
        onRefresh={handleRefresh}
      />
    )

    // Strategy column display
    expect(screen.getByTestId('suggested-strategy-2330')).toHaveTextContent('★ 均線拉回 20MA')
    expect(screen.getByTestId('reference-points-2330')).toHaveTextContent('進場: 980.00')
    expect(screen.getByTestId('reference-points-2330')).toHaveTextContent('停損: 930.00')
    expect(screen.getByTestId('reference-points-2330')).toHaveTextContent('停利: 1060.00')

    expect(screen.getByTestId('suggested-strategy-2454')).toHaveTextContent('觀望')
    expect(screen.getByTestId('trigger-condition-2454')).toHaveTextContent('收盤突破 1300 元')
    expect(screen.getByTestId('reference-points-2454')).toHaveTextContent('-')

    // Trigger sync
    const syncBtn = screen.getByTestId('sync-watchlist-btn')
    fireEvent.click(syncBtn)

    await waitFor(() => {
      expect(syncWatchlistSpy).toHaveBeenCalled()
      expect(handleRefresh).toHaveBeenCalled()
      expect(screen.getByTestId('sync-message-banner')).toHaveTextContent('同步完成：已更新 2 檔行情數據')
    })
  })
})
