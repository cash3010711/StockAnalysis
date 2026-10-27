import React, { useEffect, useState } from 'react'
import {
  createWatchlistGroup,
  deleteWatchlistGroup,
  fetchWatchlistGroups,
  removeStockFromGroup,
  syncWatchlist,
  updateStockGroups,
} from '../api/client'
import type { WatchlistGroup, WatchlistItem } from '../types/api'

interface WatchlistViewProps {
  watchlist: WatchlistItem[]
  loading?: boolean
  error?: string | null
  onSelectStock: (stockId: string) => void
  onRemove: (stockId: string) => Promise<void> | void
  onRefresh?: () => void
}

export const WatchlistView: React.FC<WatchlistViewProps> = ({
  watchlist,
  loading = false,
  error = null,
  onSelectStock,
  onRemove,
  onRefresh,
}) => {
  // Groups state
  const [groups, setGroups] = useState<WatchlistGroup[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [newGroupName, setNewGroupName] = useState<string>('')
  const [creatingGroup, setCreatingGroup] = useState<boolean>(false)

  // Group assignment modal
  const [managingStock, setManagingStock] = useState<WatchlistItem | null>(null)
  const [selectedGroupIdsInModal, setSelectedGroupIdsInModal] = useState<number[]>([])
  const [savingGroups, setSavingGroups] = useState<boolean>(false)

  // Sync state
  const [syncing, setSyncing] = useState<boolean>(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  // Load groups on mount
  useEffect(() => {
    let ignore = false
    fetchWatchlistGroups()
      .then((data) => {
        if (!ignore && Array.isArray(data)) {
          setGroups(data)
        }
      })
      .catch(() => {
        // ignore load error
      })
    return () => {
      ignore = true
    }
  }, [])

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = newGroupName.trim()
    if (!trimmed) return
    try {
      setCreatingGroup(true)
      const created = await createWatchlistGroup(trimmed)
      setGroups((prev) => [...prev, created])
      setNewGroupName('')
    } catch {
      // ignore
    } finally {
      setCreatingGroup(false)
    }
  }

  const handleDeleteGroup = async (groupId: number) => {
    try {
      await deleteWatchlistGroup(groupId)
      setGroups((prev) => prev.filter((g) => g.id !== groupId))
      if (selectedGroupId === groupId) {
        setSelectedGroupId(null)
      }
      onRefresh?.()
    } catch {
      // ignore
    }
  }

  const openManageModal = (stock: WatchlistItem) => {
    setManagingStock(stock)
    setSelectedGroupIdsInModal((stock.groups || []).map((g) => g.id))
  }

  const handleSaveStockGroups = async () => {
    if (!managingStock) return
    try {
      setSavingGroups(true)
      await updateStockGroups(managingStock.stock_id, selectedGroupIdsInModal)
      setManagingStock(null)
      onRefresh?.()
    } catch {
      // ignore
    } finally {
      setSavingGroups(false)
    }
  }

  const handleRemoveFromGroup = async (stockId: string, groupId: number) => {
    try {
      await removeStockFromGroup(stockId, groupId)
      onRefresh?.()
    } catch {
      // ignore
    }
  }

  const handleSync = async () => {
    try {
      setSyncing(true)
      setSyncMessage(null)
      const res = await syncWatchlist()
      setSyncMessage(`同步完成：已更新 ${res.synced_count} 檔行情數據`)
      onRefresh?.()
    } catch {
      setSyncMessage('同步行情失敗')
    } finally {
      setSyncing(false)
    }
  }

  const formatPct = (val?: number | null) => {
    if (val == null) return '-'
    const sign = val > 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  // Filter watchlist based on active group tab
  const filteredWatchlist = selectedGroupId === null
    ? watchlist
    : watchlist.filter((item) => (item.groups || []).some((g) => g.id === selectedGroupId))

  return (
    <div data-testid="watchlist-container" style={{ padding: '8px 0' }}>
      {/* Top Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '20px',
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
            ⭐ 自選股追蹤清單
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#64748b' }}>
            追蹤已收藏標的，掌握最新收盤價、損益變化與進出場狀態
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span
            data-testid="watchlist-count-badge"
            style={{
              padding: '4px 10px',
              borderRadius: '9999px',
              background: '#e0f2fe',
              color: '#0369a1',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            追蹤中：{watchlist.length} 檔
          </span>

          <button
            type="button"
            data-testid="sync-watchlist-btn"
            onClick={handleSync}
            disabled={syncing || loading}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: '1px solid #2563eb',
              background: '#2563eb',
              color: '#ffffff',
              fontSize: '13px',
              fontWeight: 600,
              cursor: syncing || loading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            🔄 {syncing ? '同步中...' : '同步最新行情'}
          </button>

          {onRefresh && (
            <button
              type="button"
              data-testid="refresh-watchlist-btn"
              onClick={onRefresh}
              disabled={loading || syncing}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#334155',
                fontSize: '13px',
                cursor: loading || syncing ? 'not-allowed' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              重新整理
            </button>
          )}
        </div>
      </div>

      {syncMessage && (
        <div
          data-testid="sync-message-banner"
          style={{
            padding: '8px 14px',
            marginBottom: '16px',
            borderRadius: '6px',
            background: syncMessage.includes('失敗') ? '#fef2f2' : '#f0fdf4',
            border: `1px solid ${syncMessage.includes('失敗') ? '#fca5a5' : '#bbf7d0'}`,
            color: syncMessage.includes('失敗') ? '#b91c1c' : '#15803d',
            fontSize: '13px',
            fontWeight: 500,
          }}
        >
          {syncMessage}
        </div>
      )}

      {/* Group Navigation Tabs & Creation Bar */}
      <div
        data-testid="group-nav-container"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '1px solid #e2e8f0',
        }}
      >
        {/* Group Tabs */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            data-testid="group-tab-all"
            onClick={() => setSelectedGroupId(null)}
            style={{
              padding: '6px 14px',
              borderRadius: '20px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              border: selectedGroupId === null ? '1px solid #2563eb' : '1px solid #cbd5e1',
              background: selectedGroupId === null ? '#eff6ff' : '#ffffff',
              color: selectedGroupId === null ? '#1d4ed8' : '#475569',
              transition: 'all 0.15s ease',
            }}
          >
            全部 (公用池) ({watchlist.length})
          </button>

          {groups.map((g) => {
            const count = watchlist.filter((item) => (item.groups || []).some((ig) => ig.id === g.id)).length
            const isSelected = selectedGroupId === g.id
            return (
              <div key={g.id} style={{ display: 'inline-flex', alignItems: 'center' }}>
                <button
                  type="button"
                  data-testid={`group-tab-${g.id}`}
                  onClick={() => setSelectedGroupId(g.id)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: isSelected ? '20px 0 0 20px' : '20px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: isSelected ? '1px solid #2563eb' : '1px solid #cbd5e1',
                    background: isSelected ? '#eff6ff' : '#ffffff',
                    color: isSelected ? '#1d4ed8' : '#475569',
                  }}
                >
                  {g.name} ({count})
                </button>
                {isSelected && (
                  <button
                    type="button"
                    title={`刪除群組 ${g.name}`}
                    data-testid={`delete-group-btn-${g.id}`}
                    onClick={() => handleDeleteGroup(g.id)}
                    style={{
                      padding: '6px 8px',
                      borderRadius: '0 20px 20px 0',
                      border: '1px solid #2563eb',
                      borderLeft: 'none',
                      background: '#fee2e2',
                      color: '#dc2626',
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {/* Add Group Form */}
        <form
          onSubmit={handleCreateGroup}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <input
            type="text"
            data-testid="new-group-input"
            placeholder="新增群組名稱..."
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            disabled={creatingGroup}
            style={{
              padding: '6px 10px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '13px',
              outline: 'none',
            }}
          />
          <button
            type="submit"
            data-testid="create-group-btn"
            disabled={creatingGroup || !newGroupName.trim()}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: 'none',
              background: '#2563eb',
              color: '#ffffff',
              fontSize: '13px',
              fontWeight: 600,
              cursor: creatingGroup || !newGroupName.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            + 新增群組
          </button>
        </form>
      </div>

      {/* Error display */}
      {error && (
        <div
          data-testid="watchlist-error"
          style={{
            padding: '12px 16px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            color: '#b91c1c',
            fontSize: '14px',
            marginBottom: '16px',
          }}
        >
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && watchlist.length === 0 && (
        <div
          data-testid="watchlist-loading"
          style={{
            padding: '40px',
            textAlign: 'center',
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            color: '#64748b',
          }}
        >
          載入自選股清單中...
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredWatchlist.length === 0 && (
        <div
          data-testid="watchlist-empty"
          style={{
            padding: '60px 20px',
            textAlign: 'center',
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px dashed #cbd5e1',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>⭐</div>
          <h3 style={{ fontSize: '16px', color: '#334155', marginBottom: '6px' }}>
            {selectedGroupId !== null ? '此群組內尚無股票' : '尚未加入任何自選股'}
          </h3>
          <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>
            {selectedGroupId !== null
              ? '可切換至「全部 (公用池)」點選股票列的「管理」按鈕指派至本群組。'
              : '請在「個股深度分析」頂部點擊 ⭐ 加入自選股，或由「全市場選股」結果中挑選優質標的收藏。'}
          </p>
        </div>
      )}

      {/* Watchlist Table */}
      {filteredWatchlist.length > 0 && (
        <div
          style={{
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            overflowX: 'auto',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
          }}
        >
          <table
            data-testid="watchlist-table"
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '14px',
              textAlign: 'left',
            }}
          >
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                <th style={{ padding: '12px 14px' }}>代號 / 名稱</th>
                <th style={{ padding: '12px 14px' }}>所屬群組</th>
                <th style={{ padding: '12px 14px' }}>加入日期</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>加入基準價</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>最新收盤價</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>累計損益</th>
                <th style={{ padding: '12px 14px' }}>建議策略</th>
                <th style={{ padding: '12px 14px' }}>參考點位</th>
                <th style={{ padding: '12px 14px' }}>備註</th>
                <th style={{ padding: '12px 14px', textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredWatchlist.map((item) => {
                const changePct = item.change_pct ?? item.return_pct ?? null
                const isPositive = (changePct ?? 0) > 0
                const isNegative = (changePct ?? 0) < 0
                const isEntry = item.suggested_strategy && item.suggested_strategy !== '觀望'

                return (
                  <tr
                    key={item.stock_id}
                    data-testid={`watchlist-row-${item.stock_id}`}
                    style={{
                      borderBottom: '1px solid #f1f5f9',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    {/* Stock ID & Name */}
                    <td style={{ padding: '12px 14px', fontWeight: 600, color: '#0f172a' }}>
                      <button
                        type="button"
                        data-testid={`btn-select-${item.stock_id}`}
                        onClick={() => onSelectStock(item.stock_id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          color: '#2563eb',
                          fontWeight: 600,
                          fontSize: '14px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>{item.stock_id}</span>
                        <span style={{ color: '#334155' }}>{item.stock_name}</span>
                      </button>
                    </td>

                    {/* Groups capsules */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '4px' }}>
                        {item.groups && item.groups.length > 0 ? (
                          item.groups.map((g) => (
                            <span
                              key={g.id}
                              data-testid={`group-badge-${item.stock_id}-${g.id}`}
                              style={{
                                padding: '2px 7px',
                                borderRadius: '9999px',
                                background: '#e0e7ff',
                                color: '#3730a3',
                                fontSize: '11px',
                                fontWeight: 600,
                              }}
                            >
                              {g.name}
                            </span>
                          ))
                        ) : (
                          <span style={{ fontSize: '12px', color: '#94a3b8' }}>無群組</span>
                        )}
                        <button
                          type="button"
                          data-testid={`btn-manage-groups-${item.stock_id}`}
                          onClick={() => openManageModal(item)}
                          style={{
                            background: 'none',
                            border: '1px dashed #cbd5e1',
                            borderRadius: '4px',
                            padding: '1px 5px',
                            fontSize: '11px',
                            color: '#2563eb',
                            cursor: 'pointer',
                          }}
                        >
                          管理
                        </button>
                      </div>
                    </td>

                    {/* Added Date */}
                    <td style={{ padding: '12px 14px', color: '#64748b', fontSize: '13px' }}>
                      {item.added_date || '-'}
                    </td>

                    {/* Added Price */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', color: '#334155' }}>
                      {item.added_price > 0 ? item.added_price.toFixed(2) : '-'}
                    </td>

                    {/* Current Price */}
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      {item.current_price != null ? (
                        <div>
                          <strong style={{ color: '#0f172a' }}>{item.current_price.toFixed(2)}</strong>
                          {item.current_date && (
                            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                              ({item.current_date})
                            </div>
                          )}
                        </div>
                      ) : (
                        '-'
                      )}
                    </td>

                    {/* Change % */}
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      {changePct != null ? (
                        <span
                          style={{
                            fontWeight: 600,
                            color: isPositive ? '#ef4444' : isNegative ? '#22c55e' : '#64748b',
                          }}
                        >
                          {formatPct(changePct)}
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>

                    {/* Suggested Strategy */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <span
                          data-testid={`suggested-strategy-${item.stock_id}`}
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: isEntry ? '#dcfce7' : '#f1f5f9',
                            color: isEntry ? '#15803d' : '#64748b',
                            fontWeight: 700,
                            fontSize: '12px',
                            width: 'fit-content',
                          }}
                        >
                          {isEntry ? `★ ${item.suggested_strategy}` : item.suggested_strategy || '觀望'}
                        </span>
                        {!isEntry && item.trigger_condition && (
                          <span
                            data-testid={`trigger-condition-${item.stock_id}`}
                            style={{ fontSize: '11px', color: '#64748b' }}
                          >
                            {item.trigger_condition}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Reference Points */}
                    <td style={{ padding: '12px 14px' }}>
                      {isEntry ? (
                        <div
                          data-testid={`reference-points-${item.stock_id}`}
                          style={{ fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '2px' }}
                        >
                          <div>進場: <strong>{item.entry_price != null ? item.entry_price.toFixed(2) : '-'}</strong></div>
                          <div>停損: <strong style={{ color: '#dc2626' }}>{item.stop_loss != null ? item.stop_loss.toFixed(2) : '-'}</strong></div>
                          <div>停利: <strong style={{ color: '#16a34a' }}>{item.take_profit != null ? item.take_profit.toFixed(2) : '-'}</strong></div>
                        </div>
                      ) : (
                        <div
                          data-testid={`reference-points-${item.stock_id}`}
                          style={{ fontSize: '12px', color: '#94a3b8' }}
                        >
                          -
                        </div>
                      )}
                    </td>

                    {/* Notes */}
                    <td style={{ padding: '12px 14px', color: '#64748b', fontSize: '13px' }}>
                      {item.notes || '-'}
                    </td>

                    {/* Actions */}
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', gap: '8px' }}>
                        <button
                          type="button"
                          data-testid={`btn-analyze-${item.stock_id}`}
                          onClick={() => onSelectStock(item.stock_id)}
                          style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            border: '1px solid #3b82f6',
                            background: '#eff6ff',
                            color: '#1d4ed8',
                            fontSize: '12px',
                            fontWeight: 500,
                            cursor: 'pointer',
                          }}
                        >
                          深度分析
                        </button>
                        {selectedGroupId !== null ? (
                          <button
                            type="button"
                            data-testid={`btn-remove-${item.stock_id}`}
                            onClick={() => handleRemoveFromGroup(item.stock_id, selectedGroupId)}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '4px',
                              border: '1px solid #fed7aa',
                              background: '#fff7ed',
                              color: '#c2410c',
                              fontSize: '12px',
                              fontWeight: 500,
                              cursor: 'pointer',
                            }}
                          >
                            移出群組
                          </button>
                        ) : (
                          <button
                            type="button"
                            data-testid={`btn-remove-${item.stock_id}`}
                            onClick={() => onRemove(item.stock_id)}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '4px',
                              border: '1px solid #fca5a5',
                              background: '#fef2f2',
                              color: '#b91c1c',
                              fontSize: '12px',
                              fontWeight: 500,
                              cursor: 'pointer',
                            }}
                          >
                            徹底刪除
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Group Assignment Modal */}
      {managingStock && (
        <div
          data-testid="manage-groups-modal"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
          onClick={() => setManagingStock(null)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '8px',
              padding: '20px',
              width: '360px',
              maxWidth: '90%',
              boxShadow: '0 10px 25px rgba(0, 0, 0, 0.15)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', color: '#1e293b' }}>
              管理群組 - {managingStock.stock_id} {managingStock.stock_name}
            </h3>
            {groups.length === 0 ? (
              <p style={{ fontSize: '13px', color: '#64748b' }}>
                目前尚未建立任何自訂群組，請先於上方新增群組。
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                {groups.map((g) => (
                  <label
                    key={g.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '14px',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      data-testid={`modal-group-checkbox-${g.id}`}
                      checked={selectedGroupIdsInModal.includes(g.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedGroupIdsInModal((prev) => [...prev, g.id])
                        } else {
                          setSelectedGroupIdsInModal((prev) => prev.filter((id) => id !== g.id))
                        }
                      }}
                    />
                    <span>{g.name}</span>
                  </label>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                data-testid="modal-cancel-btn"
                onClick={() => setManagingStock(null)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#475569',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                type="button"
                data-testid="modal-save-btn"
                disabled={savingGroups}
                onClick={handleSaveStockGroups}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#2563eb',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: savingGroups ? 'not-allowed' : 'pointer',
                }}
              >
                {savingGroups ? '儲存中...' : '儲存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
