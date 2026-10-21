import React from 'react'
import type { ChipsSummary, FundamentalSummary } from '../types/api'

interface LayersSummaryProps {
  fundamental: FundamentalSummary
  chips: ChipsSummary
}

export const LayersSummary: React.FC<LayersSummaryProps> = ({
  fundamental,
  chips,
}) => {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '16px',
        margin: '16px 0',
      }}
      data-testid="layers-summary"
    >
      {/* 基本面卡片 */}
      <div
        style={{
          border: `1px solid ${fundamental.passed ? '#86efac' : '#fca5a5'}`,
          borderRadius: '8px',
          background: fundamental.passed ? '#f0fdf4' : '#fef2f2',
          padding: '16px',
        }}
        data-testid="fundamental-card"
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '16px', color: '#1e293b' }}>
            基本面篩選
          </h3>
          <span
            style={{
              fontWeight: 'bold',
              fontSize: '14px',
              padding: '2px 8px',
              borderRadius: '9999px',
              background: fundamental.passed ? '#22c55e' : '#ef4444',
              color: '#ffffff',
            }}
          >
            {fundamental.passed ? '✓ 通過' : '✗ 未通過'}
          </span>
        </div>

        <div style={{ fontSize: '14px', color: '#334155', lineHeight: '1.6' }}>
          <div>
            <strong>營收年增率：</strong>{' '}
            {fundamental.revenue_yoy != null
              ? `${(fundamental.revenue_yoy * 100).toFixed(2)}%`
              : '無資料'}
          </div>
          <div>
            <strong>近四季 EPS 合計：</strong>{' '}
            {fundamental.eps_4q_sum != null
              ? `${fundamental.eps_4q_sum.toFixed(2)} 元`
              : '無資料'}
          </div>
          <div>
            <strong>負債比率：</strong>{' '}
            {fundamental.debt_ratio != null
              ? `${(fundamental.debt_ratio * 100).toFixed(2)}%`
              : '無資料'}
          </div>
          {!fundamental.passed && fundamental.reason && (
            <div
              style={{
                marginTop: '10px',
                padding: '8px',
                background: '#fee2e2',
                borderRadius: '6px',
                color: '#991b1b',
                fontSize: '13px',
              }}
              data-testid="fundamental-reason"
            >
              <strong>未通過原因：</strong> {fundamental.reason}
            </div>
          )}
        </div>
      </div>

      {/* 籌碼面卡片 */}
      <div
        style={{
          border: `1px solid ${chips.passed ? '#86efac' : '#fca5a5'}`,
          borderRadius: '8px',
          background: chips.passed ? '#f0fdf4' : '#fef2f2',
          padding: '16px',
        }}
        data-testid="chips-card"
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '16px', color: '#1e293b' }}>
            籌碼面篩選
          </h3>
          <span
            style={{
              fontWeight: 'bold',
              fontSize: '14px',
              padding: '2px 8px',
              borderRadius: '9999px',
              background: chips.passed ? '#22c55e' : '#ef4444',
              color: '#ffffff',
            }}
          >
            {chips.passed ? '✓ 通過' : '✗ 未通過'}
          </span>
        </div>

        <div style={{ fontSize: '14px', color: '#334155', lineHeight: '1.6' }}>
          <div>
            <strong>外資＋投信近 10 日：</strong>{' '}
            {chips.foreign_trust_net_buy_10d != null
              ? `${chips.foreign_trust_net_buy_10d > 0 ? '買超' : '賣超'} ${Math.abs(chips.foreign_trust_net_buy_10d).toLocaleString()} 張`
              : '無資料'}
          </div>
          <div>
            <strong>融資 10 日增幅：</strong>{' '}
            {chips.margin_increase_rate_10d != null
              ? `${(chips.margin_increase_rate_10d * 100).toFixed(2)}%`
              : '無資料'}
          </div>
          {!chips.passed && chips.reason && (
            <div
              style={{
                marginTop: '10px',
                padding: '8px',
                background: '#fee2e2',
                borderRadius: '6px',
                color: '#991b1b',
                fontSize: '13px',
              }}
              data-testid="chips-reason"
            >
              <strong>未通過原因：</strong> {chips.reason}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
