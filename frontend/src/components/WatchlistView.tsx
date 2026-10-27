import React from 'react'
import type { WatchlistItem } from '../types/api'

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
  const formatPct = (val?: number | null) => {
    if (val == null) return '-'
    const sign = val > 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

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

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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

          {onRefresh && (
            <button
              type="button"
              data-testid="refresh-watchlist-btn"
              onClick={onRefresh}
              disabled={loading}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#334155',
                fontSize: '13px',
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              🔄 重新整理
            </button>
          )}
        </div>
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
      {!loading && watchlist.length === 0 && (
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
            尚未加入任何自選股
          </h3>
          <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>
            請在「個股深度分析」頂部點擊 ⭐ 加入自選股，或由「全市場選股」結果中挑選優質標的收藏。
          </p>
        </div>
      )}

      {/* Watchlist Table */}
      {watchlist.length > 0 && (
        <div
          style={{
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            overflow: 'hidden',
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
                <th style={{ padding: '12px 14px' }}>加入日期</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>加入基準價</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>最新收盤價</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>累計損益</th>
                <th style={{ padding: '12px 14px' }}>備註</th>
                <th style={{ padding: '12px 14px', textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((item) => {
                const changePct = item.change_pct ?? item.return_pct ?? null
                const isPositive = (changePct ?? 0) > 0
                const isNegative = (changePct ?? 0) < 0

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
                          移除
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
