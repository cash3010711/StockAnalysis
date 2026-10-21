import React from 'react'
import type { StrategyItem } from '../types/api'

interface StrategyTableProps {
  strategies: StrategyItem[]
  selectedStrategyName?: string
  onSelectStrategy?: (strategyName: string) => void
}

export const StrategyTable: React.FC<StrategyTableProps> = ({
  strategies,
  selectedStrategyName,
  onSelectStrategy,
}) => {
  const formatPct = (val?: number | null) => {
    if (val == null) return '-'
    const sign = val > 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  return (
    <div style={{ marginTop: '24px', overflowX: 'auto' }} data-testid="strategy-table-container">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '18px', color: '#1e293b' }}>策略比較與回測勝率</h3>
        <span style={{ fontSize: '13px', color: '#64748b' }}>點選策略可於下方 K 線圖切換歷史交易與點位</span>
      </div>

      <table
        data-testid="strategy-table"
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '14px',
          textAlign: 'left',
          background: '#ffffff',
          borderRadius: '8px',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <thead>
          <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
            <th style={{ padding: '12px 14px' }}>策略名稱</th>
            <th style={{ padding: '12px 14px', textAlign: 'center' }}>今日狀態</th>
            <th style={{ padding: '12px 14px' }}>今日點位 / 觸發條件</th>
            <th style={{ padding: '12px 14px' }}>三層勝率 (筆數)</th>
            <th style={{ padding: '12px 14px' }}>純技術勝率 (筆數)</th>
            <th style={{ padding: '12px 14px' }}>期望值</th>
            <th style={{ padding: '12px 14px' }}>最大回檔</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((strat) => {
            const isSelected = selectedStrategyName === strat.strategy_name
            const isEntry = strat.status === '進場' || strat.action === '進場'
            const tl = strat.three_layer_stats
            const tech = strat.tech_only_stats

            return (
              <tr
                key={strat.strategy_name}
                data-testid={`strategy-row-${strat.strategy_name}`}
                onClick={() => onSelectStrategy && onSelectStrategy(strat.strategy_name)}
                style={{
                  cursor: 'pointer',
                  borderBottom: '1px solid #f1f5f9',
                  background: isSelected
                    ? isEntry
                      ? '#ecfdf5'
                      : '#eff6ff'
                    : isEntry
                    ? '#f0fdf4'
                    : '#ffffff',
                  outline: isSelected ? '2px solid #3b82f6' : 'none',
                  fontWeight: isEntry ? 600 : 'normal',
                  transition: 'background 0.15s ease',
                }}
              >
                {/* 策略名稱 */}
                <td style={{ padding: '12px 14px', color: '#0f172a' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {isSelected && <span style={{ color: '#3b82f6' }}>▶</span>}
                    <span>{strat.strategy_name}</span>
                  </div>
                </td>

                {/* 今日狀態 */}
                <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '3px 10px',
                      borderRadius: '9999px',
                      fontSize: '12px',
                      fontWeight: 'bold',
                      background: isEntry ? '#22c55e' : '#e2e8f0',
                      color: isEntry ? '#ffffff' : '#475569',
                    }}
                  >
                    {isEntry ? '★ 進場' : '觀望'}
                  </span>
                </td>

                {/* 今日點位 / 觸發條件 */}
                <td style={{ padding: '12px 14px' }}>
                  {isEntry ? (
                    <div style={{ fontSize: '13px', lineHeight: '1.4' }}>
                      <span style={{ color: '#15803d', marginRight: '8px' }}>
                        進場：{strat.entry_price ?? '-'}
                      </span>
                      <span style={{ color: '#b91c1c', marginRight: '8px' }}>
                        停損：{strat.stop_loss ?? '-'}
                      </span>
                      <span style={{ color: '#1d4ed8' }}>
                        停利：{strat.take_profit ?? '-'}
                      </span>
                    </div>
                  ) : (
                    <span style={{ color: '#64748b', fontSize: '13px' }}>
                      {strat.trigger_condition || '未達進場條件'}
                    </span>
                  )}
                </td>

                {/* 三層勝率 (筆數) */}
                <td style={{ padding: '12px 14px' }}>
                  {tl && tl.has_trades ? (
                    <div>
                      <span>
                        {tl.win_rate_pct != null ? `${tl.win_rate_pct.toFixed(1)}%` : '-'}
                      </span>
                      <span style={{ color: '#64748b', fontSize: '12px', marginLeft: '4px' }}>
                        ({tl.win_trades}/{tl.total_trades} 筆)
                      </span>
                      {tl.insufficient_sample && (
                        <span
                          style={{
                            marginLeft: '6px',
                            fontSize: '11px',
                            background: '#fef3c7',
                            color: '#b45309',
                            padding: '2px 5px',
                            borderRadius: '4px',
                            fontWeight: 'bold',
                          }}
                        >
                          樣本不足
                        </span>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: '#94a3b8' }}>無交易</span>
                  )}
                </td>

                {/* 純技術勝率 (筆數) */}
                <td style={{ padding: '12px 14px' }}>
                  {tech && tech.has_trades ? (
                    <div>
                      <span>
                        {tech.win_rate_pct != null ? `${tech.win_rate_pct.toFixed(1)}%` : '-'}
                      </span>
                      <span style={{ color: '#64748b', fontSize: '12px', marginLeft: '4px' }}>
                        ({tech.win_trades}/{tech.total_trades} 筆)
                      </span>
                      {tech.insufficient_sample && (
                        <span
                          style={{
                            marginLeft: '6px',
                            fontSize: '11px',
                            background: '#fef3c7',
                            color: '#b45309',
                            padding: '2px 5px',
                            borderRadius: '4px',
                            fontWeight: 'bold',
                          }}
                        >
                          樣本不足
                        </span>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: '#94a3b8' }}>無交易</span>
                  )}
                </td>

                {/* 期望值 */}
                <td style={{ padding: '12px 14px' }}>
                  {tl && tl.expected_value_pct != null ? (
                    <span
                      style={{
                        color: tl.expected_value_pct >= 0 ? '#16a34a' : '#dc2626',
                        fontWeight: 500,
                      }}
                    >
                      {formatPct(tl.expected_value_pct)}
                    </span>
                  ) : (
                    '-'
                  )}
                </td>

                {/* 最大回檔 */}
                <td style={{ padding: '12px 14px', color: '#b91c1c' }}>
                  {tl && tl.max_drawdown_pct != null ? formatPct(tl.max_drawdown_pct) : '-'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
