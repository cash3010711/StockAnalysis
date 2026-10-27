import React, { useState } from 'react'
import type { EquityPoint, StrategyItem } from '../types/api'

interface StrategyTableProps {
  strategies: StrategyItem[]
  selectedStrategyName?: string
  onSelectStrategy?: (strategyName: string) => void
}

const EquityCurveChart: React.FC<{
  threeLayerCurve: EquityPoint[]
  techOnlyCurve: EquityPoint[]
}> = ({ threeLayerCurve, techOnlyCurve }) => {
  if (threeLayerCurve.length === 0 && techOnlyCurve.length === 0) {
    return (
      <div
        data-testid="no-equity-curve"
        style={{
          padding: '24px',
          textAlign: 'center',
          color: '#94a3b8',
          fontSize: '13px',
          background: '#ffffff',
          borderRadius: '6px',
        }}
      >
        歷史交易資料不足，尚無累積權益曲線
      </div>
    )
  }

  // Combine dates to determine timeline
  const allEquities = [
    1.0,
    ...threeLayerCurve.map((p) => p.equity),
    ...techOnlyCurve.map((p) => p.equity),
  ]
  const minEquity = Math.min(...allEquities, 0.95)
  const maxEquity = Math.max(...allEquities, 1.05)
  const equityRange = maxEquity - minEquity || 0.1

  const svgWidth = 740
  const svgHeight = 220
  const padLeft = 55
  const padRight = 30
  const padTop = 30
  const padBottom = 35
  const plotWidth = svgWidth - padLeft - padRight
  const plotHeight = svgHeight - padTop - padBottom

  const getPoints = (curve: EquityPoint[]) => {
    if (curve.length === 0) return ''
    return curve
      .map((p, idx) => {
        const x = padLeft + (idx / (curve.length - 1 || 1)) * plotWidth
        const y = padTop + ((maxEquity - p.equity) / equityRange) * plotHeight
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }

  const tlPoints = getPoints(threeLayerCurve)
  const techPoints = getPoints(techOnlyCurve)

  const baselineY = (padTop + ((maxEquity - 1.0) / equityRange) * plotHeight).toFixed(1)

  return (
    <div
      data-testid="equity-curve-chart"
      style={{
        background: '#ffffff',
        padding: '16px',
        borderRadius: '6px',
        border: '1px solid #e2e8f0',
        overflowX: 'auto',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px',
          fontSize: '12px',
        }}
      >
        <span style={{ fontWeight: 600, color: '#334155' }}>
          權益走勢對比 (基準 = 1.00)
        </span>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#2563eb' }}>
            <span style={{ display: 'inline-block', width: '16px', height: '3px', background: '#2563eb' }} />
            三層檢驗 (風控)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f59e0b' }}>
            <span
              style={{
                display: 'inline-block',
                width: '16px',
                height: '0px',
                borderTop: '2px dashed #f59e0b',
              }}
            />
            純技術面
          </span>
        </div>
      </div>

      <svg
        data-testid="equity-curve-svg"
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
      >
        {/* Baseline 1.0 */}
        <line
          x1={padLeft}
          y1={baselineY}
          x2={svgWidth - padRight}
          y2={baselineY}
          stroke="#94a3b8"
          strokeDasharray="3 3"
          strokeWidth="1"
        />
        <text
          x={padLeft - 6}
          y={Number(baselineY) + 4}
          fill="#64748b"
          fontSize="10"
          textAnchor="end"
        >
          1.00
        </text>

        {/* Max Equity label */}
        <text
          x={padLeft - 6}
          y={padTop + 4}
          fill="#64748b"
          fontSize="10"
          textAnchor="end"
        >
          {maxEquity.toFixed(2)}
        </text>

        {/* Min Equity label */}
        <text
          x={padLeft - 6}
          y={svgHeight - padBottom}
          fill="#64748b"
          fontSize="10"
          textAnchor="end"
        >
          {minEquity.toFixed(2)}
        </text>

        {/* Axis line */}
        <line
          x1={padLeft}
          y1={padTop}
          x2={padLeft}
          y2={svgHeight - padBottom}
          stroke="#cbd5e1"
          strokeWidth="1"
        />
        <line
          x1={padLeft}
          y1={svgHeight - padBottom}
          x2={svgWidth - padRight}
          y2={svgHeight - padBottom}
          stroke="#cbd5e1"
          strokeWidth="1"
        />

        {/* Tech-only curve (Amber dashed) */}
        {techPoints && (
          <polyline
            fill="none"
            stroke="#f59e0b"
            strokeWidth="2"
            strokeDasharray="4 4"
            points={techPoints}
          />
        )}

        {/* Three-layer curve (Blue solid) */}
        {tlPoints && (
          <polyline
            fill="none"
            stroke="#2563eb"
            strokeWidth="2.5"
            points={tlPoints}
          />
        )}

        {/* Date labels at ends */}
        {threeLayerCurve.length > 0 && (
          <>
            <text
              x={padLeft}
              y={svgHeight - padBottom + 16}
              fill="#94a3b8"
              fontSize="10"
            >
              {threeLayerCurve[0].date}
            </text>
            <text
              x={svgWidth - padRight}
              y={svgHeight - padBottom + 16}
              fill="#94a3b8"
              fontSize="10"
              textAnchor="end"
            >
              {threeLayerCurve[threeLayerCurve.length - 1].date}
            </text>
          </>
        )}
      </svg>
    </div>
  )
}

export const StrategyTable: React.FC<StrategyTableProps> = ({
  strategies,
  selectedStrategyName,
  onSelectStrategy,
}) => {
  const [expandedStrategyName, setExpandedStrategyName] = useState<string | null>(null)

  const handleRowClick = (stratName: string) => {
    if (onSelectStrategy) {
      onSelectStrategy(stratName)
    }
    setExpandedStrategyName((prev) => (prev === stratName ? null : stratName))
  }

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
        <span style={{ fontSize: '13px', color: '#64748b' }}>點選策略列可展開累積權益曲線（Equity Curve）與歷史交易走勢</span>
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
            const isExpanded = expandedStrategyName === strat.strategy_name
            const isEntry = strat.status === '進場' || strat.action === '進場'
            const tl = strat.three_layer_stats
            const tech = strat.tech_only_stats

            const tlCurve = tl?.equity_curve || strat.three_layer_equity_curve || []
            const techCurve = tech?.equity_curve || strat.tech_only_equity_curve || []
            const tlFinalEquity = tlCurve.length > 0 ? `${tlCurve[tlCurve.length - 1].equity.toFixed(2)}x` : '-'
            const techFinalEquity = techCurve.length > 0 ? `${techCurve[techCurve.length - 1].equity.toFixed(2)}x` : '-'

            return (
              <React.Fragment key={strat.strategy_name}>
                <tr
                  data-testid={`strategy-row-${strat.strategy_name}`}
                  onClick={() => handleRowClick(strat.strategy_name)}
                  style={{
                    cursor: 'pointer',
                    borderBottom: isExpanded ? 'none' : '1px solid #f1f5f9',
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
                      <span style={{ color: isSelected ? '#3b82f6' : '#94a3b8', fontSize: '11px' }}>
                        {isExpanded ? '▼' : '▶'}
                      </span>
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

                {/* Expanded Equity Curve & MDD Card */}
                {isExpanded && (
                  <tr data-testid={`strategy-expanded-row-${strat.strategy_name}`}>
                    <td colSpan={7} style={{ padding: '0', borderBottom: '2px solid #e2e8f0' }}>
                      <div
                        data-testid={`equity-curve-card-${strat.strategy_name}`}
                        style={{
                          padding: '16px 20px',
                          background: '#f8fafc',
                          borderTop: '1px dashed #cbd5e1',
                        }}
                      >
                        {/* Header info */}
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '12px',
                          }}
                        >
                          <span style={{ fontWeight: 600, fontSize: '14px', color: '#1e293b' }}>
                            📊 【{strat.strategy_name}】累積權益曲線（Equity Curve）與最大回撤分析
                          </span>
                          <span style={{ fontSize: '12px', color: '#64748b' }}>
                            以逐筆交易複利累積呈現歷史淨值成長
                          </span>
                        </div>

                        {/* Summary Badges */}
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                            gap: '12px',
                            marginBottom: '14px',
                          }}
                        >
                          <div
                            style={{
                              padding: '10px 14px',
                              background: '#eff6ff',
                              borderRadius: '6px',
                              border: '1px solid #bfdbfe',
                              fontSize: '13px',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: '#1d4ed8', marginBottom: '4px' }}>
                              🛡️ 三層檢驗風控回測
                            </div>
                            <div style={{ color: '#334155' }}>
                              最終權益: <strong>{tlFinalEquity}</strong> | 最大回撤:{' '}
                              <span style={{ color: '#dc2626', fontWeight: 600 }}>
                                {formatPct(tl?.max_drawdown_pct)}
                              </span>
                            </div>
                            <div style={{ color: '#64748b', fontSize: '12px', marginTop: '2px' }}>
                              共 {tl?.total_trades ?? 0} 筆交易 ({tl?.win_trades ?? 0} 勝 /{' '}
                              {tl?.loss_trades ?? 0} 敗)
                            </div>
                          </div>

                          <div
                            style={{
                              padding: '10px 14px',
                              background: '#fffbeb',
                              borderRadius: '6px',
                              border: '1px solid #fde68a',
                              fontSize: '13px',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: '#b45309', marginBottom: '4px' }}>
                              ⚡ 純技術面回測
                            </div>
                            <div style={{ color: '#334155' }}>
                              最終權益: <strong>{techFinalEquity}</strong> | 最大回撤:{' '}
                              <span style={{ color: '#dc2626', fontWeight: 600 }}>
                                {formatPct(tech?.max_drawdown_pct)}
                              </span>
                            </div>
                            <div style={{ color: '#64748b', fontSize: '12px', marginTop: '2px' }}>
                              共 {tech?.total_trades ?? 0} 筆交易 ({tech?.win_trades ?? 0} 勝 /{' '}
                              {tech?.loss_trades ?? 0} 敗)
                            </div>
                          </div>
                        </div>

                        {/* Chart */}
                        <EquityCurveChart
                          threeLayerCurve={tlCurve}
                          techOnlyCurve={techCurve}
                        />
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
