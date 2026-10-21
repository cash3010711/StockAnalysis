import React from 'react'

interface EvaluationHeaderProps {
  stockId: string
  stockName: string
  evaluationDate: string
}

export const EvaluationHeader: React.FC<EvaluationHeaderProps> = ({
  stockId,
  stockName,
  evaluationDate,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        borderBottom: '2px solid #e2e8f0',
        paddingBottom: '12px',
        marginTop: '20px',
      }}
      data-testid="evaluation-header"
    >
      <div>
        <h2 style={{ margin: 0, fontSize: '24px', color: '#0f172a' }}>
          {stockId} {stockName}
        </h2>
      </div>
      <div style={{ color: '#475569', fontSize: '15px' }} data-testid="eval-date-text">
        評估日：<strong>{evaluationDate}</strong>（收盤後資料）
      </div>
    </div>
  )
}
