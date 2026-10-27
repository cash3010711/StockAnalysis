import React from 'react'

interface EvaluationHeaderProps {
  stockId: string
  stockName: string
  evaluationDate: string
  isInWatchlist?: boolean
  onToggleWatchlist?: (stockId: string) => void
  isWatchlistLoading?: boolean
}

export const EvaluationHeader: React.FC<EvaluationHeaderProps> = ({
  stockId,
  stockName,
  evaluationDate,
  isInWatchlist = false,
  onToggleWatchlist,
  isWatchlistLoading = false,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #e2e8f0',
        paddingBottom: '12px',
        marginTop: '20px',
      }}
      data-testid="evaluation-header"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '24px', color: '#0f172a' }}>
          {stockId} {stockName}
        </h2>

        {onToggleWatchlist && (
          <button
            type="button"
            data-testid="watchlist-toggle-btn"
            onClick={() => onToggleWatchlist(stockId)}
            disabled={isWatchlistLoading}
            title={isInWatchlist ? '自自選股清單移除' : '加入自選股清單'}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: isInWatchlist ? '1px solid #eab308' : '1px solid #cbd5e1',
              background: isInWatchlist ? '#fefce8' : '#ffffff',
              color: isInWatchlist ? '#ca8a04' : '#64748b',
              fontSize: '13px',
              fontWeight: 500,
              cursor: isWatchlistLoading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s ease',
            }}
          >
            <span>{isInWatchlist ? '⭐' : '☆'}</span>
            <span>{isInWatchlist ? '已自選' : '加自選'}</span>
          </button>
        )}
      </div>
      <div style={{ color: '#475569', fontSize: '15px' }} data-testid="eval-date-text">
        評估日：<strong>{evaluationDate}</strong>（收盤後資料）
      </div>
    </div>
  )
}
