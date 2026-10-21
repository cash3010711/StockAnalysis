import { useState } from 'react'
import { fetchAnalysis } from './api/client'
import { AlertBanner } from './components/AlertBanner'
import { Disclaimer } from './components/Disclaimer'
import { EvaluationHeader } from './components/EvaluationHeader'
import { LayersSummary } from './components/LayersSummary'
import { SearchBox } from './components/SearchBox'
import { StockChart } from './components/StockChart'
import { StrategyTable } from './components/StrategyTable'
import { ApiError } from './types/api'
import type { AnalysisResponse } from './types/api'

export function App() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [selectedStrategyName, setSelectedStrategyName] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<Error | ApiError | null>(null)

  const handleSelectStock = async (stockId: string) => {
    setLoading(true)
    setError(null)

    try {
      const data = await fetchAnalysis(stockId)
      setAnalysis(data)

      // Auto-select first strategy, prioritizing entry strategy if any
      if (data.strategies && data.strategies.length > 0) {
        const entryStrat = data.strategies.find(
          (s) => s.status === '進場' || s.action === '進場'
        )
        setSelectedStrategyName(
          entryStrat ? entryStrat.strategy_name : data.strategies[0].strategy_name
        )
      } else {
        setSelectedStrategyName('')
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err)
      } else {
        setError(new Error('發生未預期的錯誤'))
      }
      setAnalysis(null)
    } finally {
      setLoading(false)
    }
  }

  const selectedStrategy =
    analysis?.strategies.find((s) => s.strategy_name === selectedStrategyName) ||
    analysis?.strategies[0] ||
    null

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#f8fafc',
        color: '#0f172a',
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      }}
    >
      {/* Top Navigation Bar */}
      <header
        style={{
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          padding: '16px 24px',
          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '16px',
          }}
        >
          <div>
            <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
              台股波段策略分析儀
            </h1>
            <p style={{ margin: '2px 0 0 0', fontSize: '13px', color: '#64748b' }}>
              Taiwan Stock Swing Strategy Analyzer
            </p>
          </div>

          <SearchBox onSelectStock={handleSelectStock} disabled={loading} />
        </div>
      </header>

      {/* Main Content Area */}
      <main
        style={{
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '24px 20px',
        }}
      >
        {/* Loading Indicator */}
        {loading && (
          <div
            data-testid="loading-state"
            style={{
              padding: '40px',
              textAlign: 'center',
              background: '#ffffff',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              margin: '20px 0',
            }}
          >
            <div style={{ fontSize: '18px', fontWeight: 600, color: '#2563eb' }}>
              正在載入與分析資料...
            </div>
            <div style={{ marginTop: '8px', fontSize: '14px', color: '#64748b' }}>
              初次分析股票需抓取日 K、法人、融資與財報，請稍候片刻
            </div>
          </div>
        )}

        {/* Error and Warnings Banner */}
        <AlertBanner error={error} warnings={analysis?.warnings || []} />

        {/* Initial Empty Guide */}
        {!analysis && !loading && !error && (
          <div
            style={{
              padding: '60px 20px',
              textAlign: 'center',
              background: '#ffffff',
              borderRadius: '8px',
              border: '1px dashed #cbd5e1',
              margin: '32px 0',
            }}
            data-testid="welcome-box"
          >
            <h3 style={{ fontSize: '18px', color: '#334155', marginBottom: '8px' }}>
              請於上方搜尋欄輸入台股代號或名稱
            </h3>
            <p style={{ color: '#64748b', fontSize: '14px', margin: 0 }}>
              例如輸入「2330」或「台積電」，系統將進行基本面、籌碼面、技術面三層過濾與歷史回測分析。
            </p>
          </div>
        )}

        {/* Analysis Results */}
        {analysis && !loading && (
          <div>
            {/* 1. Evaluation Header */}
            <EvaluationHeader
              stockId={analysis.stock_id}
              stockName={analysis.stock_name}
              evaluationDate={analysis.evaluation_date}
            />

            {/* 2. Fundamental and Chips Layer Summaries */}
            <LayersSummary
              fundamental={analysis.fundamental}
              chips={analysis.chips}
            />

            {/* 3. Strategy Comparison Table */}
            <StrategyTable
              strategies={analysis.strategies}
              selectedStrategyName={selectedStrategyName}
              onSelectStrategy={setSelectedStrategyName}
            />

            {/* 4. Candlestick Chart with Volume, Markers and Price Lines */}
            <StockChart
              ohlcv={analysis.ohlcv}
              selectedStrategy={selectedStrategy}
            />
          </div>
        )}
      </main>

      {/* Fixed Disclaimer at bottom */}
      <Disclaimer />
    </div>
  )
}

export default App
