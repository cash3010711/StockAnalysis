import React, { useEffect, useMemo, useRef, useState } from 'react'
import { fetchScannerOptions, streamMarketScan } from '../api/client'
import type {
  ScanMatchedStock,
  ScanOptionPool,
  ScanStreamEvent,
} from '../types/api'

interface MarketScannerProps {
  onSelectStock: (stockId: string) => void
}

const DEFAULT_POOLS: ScanOptionPool[] = [
  { id: 'cached', name: '本機已快取股票' },
  { id: 'tw50', name: '熱門權值／台灣 50 代表股' },
  { id: 'all', name: '全市場上市櫃普通股' },
  { id: 'twse', name: '僅上市普通股' },
  { id: 'tpex', name: '僅上櫃普通股' },
]

const DEFAULT_STRATEGIES: string[] = [
  '均線多頭排列',
  '均線拉回 20MA',
  '帶量突破 20 日新高',
  'KD 低檔金叉',
  'MACD 柱狀圖翻紅',
]

type SortField =
  | 'stock_id'
  | 'close'
  | 'best_win_rate_pct'
  | 'best_avg_return_pct'
  | 'foreign_trust_net_buy_10d'
  | 'revenue_yoy'

type SortDirection = 'asc' | 'desc'

export const MarketScanner: React.FC<MarketScannerProps> = ({ onSelectStock }) => {
  // Option lists
  const [pools, setPools] = useState<ScanOptionPool[]>(DEFAULT_POOLS)
  const [industries, setIndustries] = useState<string[]>([])
  const [strategiesList, setStrategiesList] = useState<string[]>(DEFAULT_STRATEGIES)
  const [cachedCount, setCachedCount] = useState<number>(0)

  // Filter configurations
  const [selectedPool, setSelectedPool] = useState<string>('cached')
  const [selectedIndustry, setSelectedIndustry] = useState<string>('')
  const [syncLatest, setSyncLatest] = useState<boolean>(false)
  const [requireFundamental, setRequireFundamental] = useState<boolean>(true)
  const [requireChips, setRequireChips] = useState<boolean>(true)
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(DEFAULT_STRATEGIES)

  // Execution & Progress state
  const [scanning, setScanning] = useState<boolean>(false)
  const [scanStatus, setScanStatus] = useState<
    'idle' | 'scanning' | 'completed' | 'aborted' | 'error'
  >('idle')
  const [total, setTotal] = useState<number>(0)
  const [scanned, setScanned] = useState<number>(0)
  const [matchedCount, setMatchedCount] = useState<number>(0)
  const [currentStock, setCurrentStock] = useState<{ id: string; name: string } | null>(null)
  const [quotaExceeded, setQuotaExceeded] = useState<boolean>(false)
  const [warnings, setWarnings] = useState<string[]>([])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [results, setResults] = useState<ScanMatchedStock[]>([])

  // Sort state
  const [sortField, setSortField] = useState<SortField>('best_win_rate_pct')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const abortControllerRef = useRef<AbortController | null>(null)

  // Load scanner options on mount
  useEffect(() => {
    let ignore = false
    fetchScannerOptions()
      .then((opts) => {
        if (ignore) return
        if (opts.pools && opts.pools.length > 0) setPools(opts.pools)
        if (opts.industries && opts.industries.length > 0) setIndustries(opts.industries)
        if (opts.strategies && opts.strategies.length > 0) {
          setStrategiesList(opts.strategies)
          setSelectedStrategies(opts.strategies)
        }
        setCachedCount(opts.cached_count)
        if (opts.defaults) {
          setSelectedPool(opts.defaults.pool || (opts.cached_count > 0 ? 'cached' : 'tw50'))
          if (opts.defaults.sync_latest != null) setSyncLatest(opts.defaults.sync_latest)
          if (opts.defaults.require_fundamental != null)
            setRequireFundamental(opts.defaults.require_fundamental)
          if (opts.defaults.require_chips != null)
            setRequireChips(opts.defaults.require_chips)
        }
      })
      .catch(() => {
        // Fallback to default state silently
      })
    return () => {
      ignore = true
    }
  }, [])

  // Clean up abort on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  const handleToggleStrategy = (strat: string) => {
    if (selectedStrategies.includes(strat)) {
      setSelectedStrategies(selectedStrategies.filter((s) => s !== strat))
    } else {
      setSelectedStrategies([...selectedStrategies, strat])
    }
  }

  const handleSelectAllStrategies = () => {
    setSelectedStrategies([...strategiesList])
  }

  const handleDeselectAllStrategies = () => {
    setSelectedStrategies([])
  }

  const handleStartScan = async () => {
    if (scanning) return
    const controller = new AbortController()
    abortControllerRef.current = controller

    setScanning(true)
    setScanStatus('scanning')
    setErrorMessage(null)
    setWarnings([])
    setQuotaExceeded(false)
    setTotal(0)
    setScanned(0)
    setMatchedCount(0)
    setCurrentStock(null)
    setResults([])

    try {
      await streamMarketScan(
        {
          pool: selectedPool,
          industry_category: selectedIndustry || null,
          sync_latest: syncLatest,
          require_fundamental: requireFundamental,
          require_chips: requireChips,
          strategies: selectedStrategies,
        },
        (event: ScanStreamEvent) => {
          if (event.event === 'start') {
            setTotal(event.total)
          } else if (event.event === 'match') {
            setResults((prev) => [...prev, event.data])
            setMatchedCount(event.matched_count)
            setScanned(event.current)
            setTotal(event.total)
          } else if (event.event === 'progress') {
            setScanned(event.current)
            setTotal(event.total)
            setCurrentStock({ id: event.stock_id, name: event.stock_name })
            setMatchedCount(event.matched_count)
            if (event.quota_exceeded) {
              setQuotaExceeded(true)
            }
          } else if (event.event === 'done') {
            setTotal(event.total)
            setScanned(event.scanned)
            setMatchedCount(event.matched_count)
            if (event.quota_exceeded) {
              setQuotaExceeded(true)
            }
            if (event.warnings && event.warnings.length > 0) {
              setWarnings(event.warnings)
            }
            setScanStatus('completed')
            setScanning(false)
          }
        },
        controller.signal
      )

      if (!controller.signal.aborted) {
        setScanStatus('completed')
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) {
        setScanStatus('aborted')
      } else {
        const msg = err instanceof Error ? err.message : '掃描發生異常'
        setErrorMessage(msg)
        setScanStatus('error')
      }
    } finally {
      setScanning(false)
      abortControllerRef.current = null
    }
  }

  const handleAbortScan = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setScanning(false)
    setScanStatus('aborted')
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  // Sorted results
  const sortedResults = useMemo(() => {
    const list = [...results]
    list.sort((a, b) => {
      let aVal = a[sortField]
      let bVal = b[sortField]

      if (sortField === 'stock_id') {
        const cmp = String(aVal ?? '').localeCompare(String(bVal ?? ''))
        return sortDirection === 'asc' ? cmp : -cmp
      }

      // Numeric comparison with null handling
      const aNum = typeof aVal === 'number' ? aVal : null
      const bNum = typeof bVal === 'number' ? bVal : null

      if (aNum === null && bNum === null) return 0
      if (aNum === null) return 1
      if (bNum === null) return -1

      return sortDirection === 'asc' ? aNum - bNum : bNum - aNum
    })
    return list
  }, [results, sortField, sortDirection])

  const progressPercent = total > 0 ? Math.min(100, Math.round((scanned / total) * 100)) : 0

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return '↕'
    return sortDirection === 'asc' ? '▲' : '▼'
  }

  return (
    <div data-testid="market-scanner" style={{ marginTop: '8px' }}>
      {/* Configuration Control Panel */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '8px',
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
          marginBottom: '20px',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
            borderBottom: '1px solid #f1f5f9',
            paddingBottom: '12px',
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#1e293b' }}>
              全市場選股條件設定
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
              透過兩階段快速技術初篩與基本面／籌碼面三層驗證，即時掃描並排序潛力標的
            </p>
          </div>
          <div style={{ fontSize: '13px', color: '#475569', background: '#f8fafc', padding: '6px 12px', borderRadius: '6px' }}>
            本機快取股票：<strong>{cachedCount}</strong> 檔
          </div>
        </div>

        {/* Row 1: Stock Pool, Industry & Sync Toggle */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '16px',
            marginBottom: '18px',
          }}
        >
          <div>
            <label
              htmlFor="scanner-pool-select"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#334155', marginBottom: '6px' }}
            >
              股票池範圍
            </label>
            <select
              id="scanner-pool-select"
              data-testid="pool-select"
              value={selectedPool}
              disabled={scanning}
              onChange={(e) => setSelectedPool(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '14px',
                background: '#ffffff',
                backgroundColor: '#ffffff',
                color: '#0f172a',
                colorScheme: 'light',
              }}
            >
              {pools.map((p) => (
                <option
                  key={p.id}
                  value={p.id}
                  style={{ color: '#0f172a', backgroundColor: '#ffffff' }}
                >
                  {p.name} {p.id === 'cached' ? `(${cachedCount}檔)` : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="scanner-industry-select"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#334155', marginBottom: '6px' }}
            >
              特定產業過濾
            </label>
            <select
              id="scanner-industry-select"
              data-testid="industry-select"
              value={selectedIndustry}
              disabled={scanning}
              onChange={(e) => setSelectedIndustry(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '14px',
                background: '#ffffff',
                backgroundColor: '#ffffff',
                color: '#0f172a',
                colorScheme: 'light',
              }}
            >
              <option value="" style={{ color: '#0f172a', backgroundColor: '#ffffff' }}>
                全部產業（不限）
              </option>
              {industries.map((ind) => (
                <option
                  key={ind}
                  value={ind}
                  style={{ color: '#0f172a', backgroundColor: '#ffffff' }}
                >
                  {ind}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#334155', marginBottom: '6px' }}
            >
              資料更新模式
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid #e2e8f0',
                background: syncLatest ? '#eff6ff' : '#f8fafc',
                cursor: scanning ? 'not-allowed' : 'pointer',
                fontSize: '14px',
              }}
            >
              <input
                type="checkbox"
                data-testid="sync-latest-checkbox"
                checked={syncLatest}
                disabled={scanning}
                onChange={(e) => setSyncLatest(e.target.checked)}
              />
              <span style={{ fontWeight: 500, color: syncLatest ? '#1d4ed8' : '#475569' }}>
                自動向 FinMind 同步最新資料
              </span>
            </label>
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
              {syncLatest
                ? '若遭遇每小時 600 次額度上限，將自動降級以本機快取繼續掃描'
                : '僅掃描本機快取資料庫（毫秒級極速掃描）'}
            </div>
          </div>
        </div>

        {/* Row 2: Fundamental & Chips Layers */}
        <div
          style={{
            background: '#f8fafc',
            borderRadius: '6px',
            padding: '12px 16px',
            marginBottom: '18px',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginBottom: '8px' }}>
            濾網條件勾選
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
              <input
                type="checkbox"
                data-testid="require-fundamental-checkbox"
                checked={requireFundamental}
                disabled={scanning}
                onChange={(e) => setRequireFundamental(e.target.checked)}
              />
              <span style={{ color: '#1e293b' }}>
                要求<strong>基本面合格</strong>
                <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '4px' }}>
                  （月營收年增率 &gt; 0% 且 近4季 EPS &gt; 0）
                </span>
              </span>
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
              <input
                type="checkbox"
                data-testid="require-chips-checkbox"
                checked={requireChips}
                disabled={scanning}
                onChange={(e) => setRequireChips(e.target.checked)}
              />
              <span style={{ color: '#1e293b' }}>
                要求<strong>籌碼面合格</strong>
                <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '4px' }}>
                  （近10日法人買超 &gt; 0 或 融資增幅 &lt; 20%）
                </span>
              </span>
            </label>
          </div>
        </div>

        {/* Row 3: 5 Technical Strategies */}
        <div style={{ marginBottom: '18px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>
              技術策略勾選（任一觸發即納入候選，已勾選 {selectedStrategies.length} / {strategiesList.length} 項）
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={handleSelectAllStrategies}
                disabled={scanning}
                style={{
                  fontSize: '12px',
                  background: 'none',
                  border: 'none',
                  color: '#2563eb',
                  cursor: 'pointer',
                  padding: '2px 6px',
                }}
              >
                全選
              </button>
              <span style={{ color: '#cbd5e1' }}>|</span>
              <button
                type="button"
                onClick={handleDeselectAllStrategies}
                disabled={scanning}
                style={{
                  fontSize: '12px',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                  padding: '2px 6px',
                }}
              >
                取消全選
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {strategiesList.map((strat) => {
              const checked = selectedStrategies.includes(strat)
              return (
                <label
                  key={strat}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 12px',
                    borderRadius: '20px',
                    border: `1px solid ${checked ? '#93c5fd' : '#cbd5e1'}`,
                    background: checked ? '#eff6ff' : '#ffffff',
                    cursor: scanning ? 'not-allowed' : 'pointer',
                    fontSize: '13px',
                    color: checked ? '#1e40af' : '#475569',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <input
                    type="checkbox"
                    data-testid={`strategy-checkbox-${strat}`}
                    checked={checked}
                    disabled={scanning}
                    onChange={() => handleToggleStrategy(strat)}
                  />
                  <span>{strat}</span>
                </label>
              )
            })}
          </div>
          {selectedStrategies.length === 0 && (
            <div style={{ fontSize: '12px', color: '#dc2626', marginTop: '6px' }}>
              ⚠️ 請至少勾選一項技術策略以啟動篩選
            </div>
          )}
        </div>

        {/* Row 4: Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            type="button"
            data-testid="start-scan-btn"
            onClick={handleStartScan}
            disabled={scanning || selectedStrategies.length === 0}
            style={{
              padding: '10px 24px',
              borderRadius: '6px',
              background: scanning || selectedStrategies.length === 0 ? '#94a3b8' : '#2563eb',
              color: '#ffffff',
              border: 'none',
              fontWeight: 600,
              fontSize: '15px',
              cursor: scanning || selectedStrategies.length === 0 ? 'not-allowed' : 'pointer',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
              transition: 'background 0.2s',
            }}
          >
            {scanning ? '掃描進行中...' : '開始選股掃描'}
          </button>

          {scanning && (
            <button
              type="button"
              data-testid="abort-scan-btn"
              onClick={handleAbortScan}
              style={{
                padding: '10px 20px',
                borderRadius: '6px',
                background: '#fee2e2',
                color: '#dc2626',
                border: '1px solid #fecaca',
                fontWeight: 600,
                fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              中止掃描
            </button>
          )}

          {scanStatus === 'aborted' && (
            <span style={{ fontSize: '13px', color: '#dc2626', fontWeight: 500 }}>
              已手動中止掃描，保留目前已找到的結果
            </span>
          )}
          {scanStatus === 'completed' && (
            <span style={{ fontSize: '13px', color: '#16a34a', fontWeight: 500 }}>
              ✓ 掃描完成！共評估 {scanned} 檔，找到 {matchedCount} 檔符合標的
            </span>
          )}
        </div>
      </div>

      {/* Progress & Quota Alert Bar */}
      {(scanning || scanStatus === 'completed' || scanStatus === 'aborted') && (
        <div
          data-testid="scan-status-info"
          style={{
            background: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            padding: '16px 20px',
            marginBottom: '20px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
              fontSize: '14px',
            }}
          >
            <div>
              <span style={{ fontWeight: 600, color: '#1e293b' }}>
                進度：{scanned} / {total || scanned || 0} 檔 ({progressPercent}%)
              </span>
              {currentStock && scanning && (
                <span style={{ marginLeft: '12px', color: '#64748b' }}>
                  目前評估：<strong>{currentStock.id} {currentStock.name}</strong>
                </span>
              )}
            </div>
            <div style={{ fontWeight: 600, color: '#2563eb' }}>
              符合條件：{matchedCount} 檔
            </div>
          </div>

          {/* Progress Bar */}
          <div
            style={{
              width: '100%',
              height: '10px',
              background: '#f1f5f9',
              borderRadius: '5px',
              overflow: 'hidden',
            }}
          >
            <div
              data-testid="scan-progress-bar"
              style={{
                width: `${progressPercent}%`,
                height: '100%',
                background: scanStatus === 'aborted' ? '#f59e0b' : '#2563eb',
                transition: 'width 0.2s ease',
              }}
            />
          </div>

          {/* Quota Exceeded Warning */}
          {quotaExceeded && (
            <div
              data-testid="quota-exceeded-alert"
              style={{
                marginTop: '12px',
                padding: '10px 14px',
                background: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: '6px',
                color: '#92400e',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>⚠️</span>
              <span>
                <strong>FinMind API 請求額度已達上限（600次/小時）</strong>：後續標的已自動降級為本機快取模式評估，不會中斷掃描。
              </span>
            </div>
          )}

          {warnings.length > 0 && !quotaExceeded && (
            <div style={{ marginTop: '10px', fontSize: '13px', color: '#b45309' }}>
              {warnings.map((w, i) => (
                <div key={i}>⚠️ {w}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div
          data-testid="scan-error-alert"
          style={{
            padding: '12px 16px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            color: '#dc2626',
            fontSize: '14px',
            marginBottom: '20px',
          }}
        >
          ❌ 掃描失敗：{errorMessage}
        </div>
      )}

      {/* Matched Stocks Table */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '8px',
          border: '1px solid #e2e8f0',
          padding: '20px',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '14px',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#1e293b' }}>
            符合條件股票清單 ({sortedResults.length} 檔)
          </h3>
          <span style={{ fontSize: '13px', color: '#64748b' }}>
            點擊股票代號或「深度分析」可直接切換至個股 K 線分析
          </span>
        </div>

        {sortedResults.length === 0 ? (
          <div
            style={{
              padding: '48px 20px',
              textAlign: 'center',
              color: '#94a3b8',
              fontSize: '14px',
              background: '#f8fafc',
              borderRadius: '6px',
              border: '1px dashed #e2e8f0',
            }}
          >
            {scanning
              ? '正在即時搜尋符合條件之股票...'
              : scanStatus === 'completed'
              ? '本次掃描範圍內無符合全部勾選條件之股票，可嘗試放寬基本面／籌碼面條件或切換股票池'
              : '尚未執行掃描，請點選上方「開始選股掃描」啟動搜尋'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table
              data-testid="scanner-results-table"
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '13px',
                textAlign: 'left',
              }}
            >
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                  <th
                    onClick={() => handleSort('stock_id')}
                    data-testid="sort-stock_id"
                    style={{ padding: '10px 12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    股票代號／名稱 {getSortIcon('stock_id')}
                  </th>
                  <th
                    onClick={() => handleSort('close')}
                    data-testid="sort-close"
                    style={{ padding: '10px 12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    收盤價 {getSortIcon('close')}
                  </th>
                  <th style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>今日觸發策略</th>
                  <th style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>建議進出場點位</th>
                  <th
                    onClick={() => handleSort('revenue_yoy')}
                    data-testid="sort-revenue_yoy"
                    style={{ padding: '10px 12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    基本面指標 {getSortIcon('revenue_yoy')}
                  </th>
                  <th
                    onClick={() => handleSort('foreign_trust_net_buy_10d')}
                    data-testid="sort-foreign_trust_net_buy_10d"
                    style={{ padding: '10px 12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    籌碼面指標 {getSortIcon('foreign_trust_net_buy_10d')}
                  </th>
                  <th
                    onClick={() => handleSort('best_win_rate_pct')}
                    data-testid="sort-best_win_rate_pct"
                    style={{ padding: '10px 12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    歷史勝率 {getSortIcon('best_win_rate_pct')}
                  </th>
                  <th
                    onClick={() => handleSort('best_avg_return_pct')}
                    data-testid="sort-best_avg_return_pct"
                    style={{ padding: '10px 12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    平均報酬 {getSortIcon('best_avg_return_pct')}
                  </th>
                  <th style={{ padding: '10px 12px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((stock) => {
                  const revYoyStr =
                    stock.revenue_yoy != null
                      ? `${(stock.revenue_yoy * 100).toFixed(1)}%`
                      : '-'
                  const epsStr =
                    stock.eps_4q_sum != null ? `${stock.eps_4q_sum.toFixed(2)}` : '-'
                  const buy10dStr =
                    stock.foreign_trust_net_buy_10d != null
                      ? `${stock.foreign_trust_net_buy_10d > 0 ? '+' : ''}${stock.foreign_trust_net_buy_10d.toLocaleString()}張`
                      : '-'
                  const winRateStr =
                    stock.best_win_rate_pct != null
                      ? `${stock.best_win_rate_pct.toFixed(1)}%`
                      : '-'
                  const avgRetStr =
                    stock.best_avg_return_pct != null
                      ? `${stock.best_avg_return_pct > 0 ? '+' : ''}${stock.best_avg_return_pct.toFixed(2)}%`
                      : '-'

                  return (
                    <tr
                      key={stock.stock_id}
                      data-testid={`stock-row-${stock.stock_id}`}
                      style={{
                        borderBottom: '1px solid #f1f5f9',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#f8fafc'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent'
                      }}
                    >
                      {/* 1. Stock ID & Name */}
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            type="button"
                            onClick={() => onSelectStock(stock.stock_id)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#2563eb',
                              fontWeight: 700,
                              fontSize: '14px',
                              cursor: 'pointer',
                              padding: 0,
                              textDecoration: 'underline',
                            }}
                          >
                            {stock.stock_id} {stock.stock_name}
                          </button>
                        </div>
                        <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              padding: '1px 5px',
                              background: '#f1f5f9',
                              color: '#475569',
                              borderRadius: '4px',
                            }}
                          >
                            {stock.market || stock.type?.toUpperCase()}
                          </span>
                          {stock.industry_category && (
                            <span
                              style={{
                                fontSize: '11px',
                                padding: '1px 5px',
                                background: '#f1f5f9',
                                color: '#475569',
                                borderRadius: '4px',
                              }}
                            >
                              {stock.industry_category}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* 2. Close Price & Date */}
                      <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>
                        <div style={{ fontWeight: 600, color: '#1e293b' }}>
                          ${stock.close.toFixed(2)}
                        </div>
                        <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                          {stock.evaluation_date}
                        </div>
                      </td>

                      {/* 3. Triggered Strategies */}
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', maxWidth: '220px' }}>
                          {stock.triggered_strategies.map((strat) => (
                            <span
                              key={strat}
                              style={{
                                fontSize: '11px',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                background: '#eff6ff',
                                color: '#1e40af',
                                border: '1px solid #bfdbfe',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {strat}
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* 4. Entry / SL / TP Levels */}
                      <td style={{ padding: '12px', fontSize: '12px', whiteSpace: 'nowrap' }}>
                        <div>進：<strong>{stock.entry_price ?? '-'}</strong></div>
                        <div style={{ color: '#dc2626' }}>
                          損：{stock.stop_loss ?? '-'}
                        </div>
                        <div style={{ color: '#16a34a' }}>
                          利：{stock.take_profit ?? '-'}
                        </div>
                      </td>

                      {/* 5. Fundamental Summary */}
                      <td style={{ padding: '12px', fontSize: '12px', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 600,
                              padding: '1px 5px',
                              borderRadius: '3px',
                              background: stock.fundamental_passed ? '#dcfce7' : '#fee2e2',
                              color: stock.fundamental_passed ? '#15803d' : '#b91c1c',
                            }}
                          >
                            {stock.fundamental_passed ? '合格' : '未過'}
                          </span>
                          <span>營收：{revYoyStr}</span>
                        </div>
                        <div style={{ color: '#64748b', marginTop: '2px' }}>
                          EPS：{epsStr}
                        </div>
                      </td>

                      {/* 6. Chips Summary */}
                      <td style={{ padding: '12px', fontSize: '12px', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 600,
                              padding: '1px 5px',
                              borderRadius: '3px',
                              background: stock.chips_passed ? '#dcfce7' : '#fee2e2',
                              color: stock.chips_passed ? '#15803d' : '#b91c1c',
                            }}
                          >
                            {stock.chips_passed ? '合格' : '未過'}
                          </span>
                          <span>法人：{buy10dStr}</span>
                        </div>
                        {stock.margin_increase_rate_10d != null && (
                          <div style={{ color: '#64748b', marginTop: '2px' }}>
                            融資：{(stock.margin_increase_rate_10d * 100).toFixed(1)}%
                          </div>
                        )}
                      </td>

                      {/* 7. Backtest Win Rate */}
                      <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>
                        <div
                          style={{
                            fontWeight: 600,
                            color:
                              (stock.best_win_rate_pct ?? 0) >= 60
                                ? '#16a34a'
                                : (stock.best_win_rate_pct ?? 0) >= 50
                                ? '#2563eb'
                                : '#475569',
                          }}
                        >
                          {winRateStr}
                        </div>
                        {stock.best_strategy_name && (
                          <div style={{ fontSize: '11px', color: '#94a3b8', maxWidth: '110px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {stock.best_strategy_name}
                          </div>
                        )}
                      </td>

                      {/* 8. Avg Return */}
                      <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>
                        <div
                          style={{
                            fontWeight: 600,
                            color:
                              (stock.best_avg_return_pct ?? 0) > 0
                                ? '#16a34a'
                                : (stock.best_avg_return_pct ?? 0) < 0
                                ? '#dc2626'
                                : '#475569',
                          }}
                        >
                          {avgRetStr}
                        </div>
                      </td>

                      {/* 9. Action Button */}
                      <td style={{ padding: '12px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                        <button
                          type="button"
                          onClick={() => onSelectStock(stock.stock_id)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            background: '#2563eb',
                            color: '#ffffff',
                            border: 'none',
                            fontSize: '12px',
                            fontWeight: 500,
                            cursor: 'pointer',
                          }}
                        >
                          深度分析
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
