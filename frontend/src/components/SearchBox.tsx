import React, { useEffect, useRef, useState } from 'react'
import { searchStocks } from '../api/client'
import type { StockLookupItem } from '../types/api'

interface SearchBoxProps {
  onSelectStock: (stockId: string, stockName?: string) => void
  disabled?: boolean
  initialValue?: string
}

export const SearchBox: React.FC<SearchBoxProps> = ({
  onSelectStock,
  disabled = false,
  initialValue = '',
}) => {
  const [query, setQuery] = useState(initialValue)
  const [candidates, setCandidates] = useState<StockLookupItem[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setQuery(val)
    if (!val.trim()) {
      setCandidates([])
      setIsOpen(false)
      setIsLoading(false)
      setHasSearched(false)
      setErrorMessage(null)
    } else {
      setIsLoading(true)
      setErrorMessage(null)
    }
  }

  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      return
    }

    const timer = setTimeout(async () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      const controller = new AbortController()
      abortControllerRef.current = controller

      try {
        const results = await searchStocks(trimmed, controller.signal)
        setCandidates(results)
        setIsOpen(true)
        setHasSearched(true)
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        setErrorMessage(err instanceof Error ? err.message : '查詢失敗')
        setCandidates([])
        setIsOpen(true)
        setHasSearched(true)
      } finally {
        setIsLoading(false)
      }
    }, 250)

    return () => {
      clearTimeout(timer)
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [query])

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const handleSelect = (item: StockLookupItem) => {
    setQuery(`${item.stock_id} ${item.stock_name}`)
    setIsOpen(false)
    onSelectStock(item.stock_id, item.stock_name)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const trimmed = query.trim()
      if (candidates.length > 0) {
        handleSelect(candidates[0])
      } else if (/^\d{4}$/.test(trimmed)) {
        setIsOpen(false)
        onSelectStock(trimmed)
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', width: '100%', maxWidth: '540px' }}
      className="search-box-container"
    >
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => {
            if (candidates.length > 0 || hasSearched) setIsOpen(true)
          }}
          onKeyDown={handleKeyDown}
          placeholder="輸入代號或名稱（例如 2330、台積電）"
          disabled={disabled}
          aria-label="股票搜尋"
          style={{
            flex: 1,
            padding: '10px 14px',
            fontSize: '15px',
            borderRadius: '6px',
            border: '1px solid #cbd5e1',
            outline: 'none',
            boxSizing: 'border-box',
            color: '#0f172a',
            backgroundColor: '#ffffff',
            colorScheme: 'light',
          }}
        />
        {isLoading && (
          <span
            style={{
              position: 'absolute',
              right: '12px',
              top: '12px',
              fontSize: '13px',
              color: '#94a3b8',
            }}
          >
            搜尋中...
          </span>
        )}
      </div>

      {isOpen && (
        <div
          role="listbox"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            background: '#ffffff',
            border: '1px solid #cbd5e1',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
            maxHeight: '320px',
            overflowY: 'auto',
            zIndex: 100,
          }}
        >
          {errorMessage && (
            <div style={{ padding: '12px 16px', color: '#dc2626', fontSize: '14px' }}>
              {errorMessage}
            </div>
          )}

          {!errorMessage && candidates.length === 0 && hasSearched && !isLoading && (
            <div
              style={{
                padding: '12px 16px',
                color: '#64748b',
                fontSize: '14px',
                textAlign: 'center',
              }}
            >
              查無符合股票
            </div>
          )}

          {candidates.map((item) => (
            <div
              key={item.stock_id}
              role="option"
              aria-selected="false"
              onClick={() => handleSelect(item)}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 16px',
                cursor: 'pointer',
                borderBottom: '1px solid #f1f5f9',
                fontSize: '14px',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f8fafc'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#ffffff'
              }}
            >
              <div>
                <strong style={{ color: '#0f172a', marginRight: '8px' }}>
                  {item.stock_id}
                </strong>
                <span style={{ color: '#334155' }}>{item.stock_name}</span>
                {item.industry_category && (
                  <span
                    style={{
                      marginLeft: '8px',
                      fontSize: '12px',
                      color: '#64748b',
                    }}
                  >
                    ({item.industry_category})
                  </span>
                )}
              </div>
              <span
                style={{
                  fontSize: '12px',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: item.market === 'TWSE' ? '#e0f2fe' : '#fef3c7',
                  color: item.market === 'TWSE' ? '#0369a1' : '#b45309',
                  fontWeight: 500,
                }}
              >
                {item.market}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
