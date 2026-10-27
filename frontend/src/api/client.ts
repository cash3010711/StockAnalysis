import { ApiError } from '../types/api'
import type {
  AnalysisResponse,
  ApiErrorData,
  ScannerOptionsResponse,
  ScanRequest,
  ScanRunResponse,
  ScanStreamEvent,
  StockLookupItem,
  WatchlistItem,
} from '../types/api'

export async function searchStocks(
  query: string,
  signal?: AbortSignal
): Promise<StockLookupItem[]> {
  const trimmed = query.trim()
  if (!trimmed) {
    return []
  }

  const res = await fetch(`/api/stocks?q=${encodeURIComponent(trimmed)}`, { signal })
  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore json parse error
    }
    throw new ApiError(res.status, errorData)
  }

  const items: StockLookupItem[] = await res.json()
  return items.slice(0, 10)
}

export async function fetchAnalysis(
  stockId: string,
  signal?: AbortSignal
): Promise<AnalysisResponse> {
  const trimmed = stockId.trim()
  if (!trimmed) {
    throw new ApiError(400, {
      code: 'INVALID_STOCK_ID',
      message: '請輸入股票代號',
    })
  }

  const res = await fetch(`/api/analysis/${encodeURIComponent(trimmed)}`, { signal })
  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore json parse error
    }
    throw new ApiError(res.status, errorData)
  }

  return await res.json()
}

export async function fetchScannerOptions(
  signal?: AbortSignal
): Promise<ScannerOptionsResponse> {
  const res = await fetch('/api/scanner/options', { signal })
  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorData)
  }
  return await res.json()
}

export async function runMarketScan(
  params: ScanRequest,
  signal?: AbortSignal
): Promise<ScanRunResponse> {
  const res = await fetch('/api/scanner/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  })

  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorData)
  }

  return await res.json()
}

export async function streamMarketScan(
  params: ScanRequest,
  onEvent: (event: ScanStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch('/api/scanner/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
    signal,
  })

  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorData)
  }

  if (!res.body) {
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed) {
          try {
            const parsed = JSON.parse(trimmed) as ScanStreamEvent
            onEvent(parsed)
          } catch {
            // ignore malformed line
          }
        }
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) {
      try {
        const parsed = JSON.parse(buffer.trim()) as ScanStreamEvent
        onEvent(parsed)
      } catch {
        // ignore
      }
    }
  } catch (err: unknown) {
    if ((err as Error)?.name === 'AbortError' || signal?.aborted) {
      return
    }
    throw err
  }
}

export async function fetchWatchlist(
  signal?: AbortSignal
): Promise<WatchlistItem[]> {
  const res = await fetch('/api/watchlist', { signal })
  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorData)
  }
  return await res.json()
}

export async function addToWatchlist(
  payload: {
    stock_id: string
    stock_name?: string
    added_date?: string
    added_price?: number
    notes?: string
  },
  signal?: AbortSignal
): Promise<WatchlistItem> {
  const res = await fetch('/api/watchlist', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorData)
  }

  return await res.json()
}

export async function removeFromWatchlist(
  stockId: string,
  signal?: AbortSignal
): Promise<{ success: boolean; stock_id: string; message: string }> {
  const trimmed = stockId.trim()
  const res = await fetch(`/api/watchlist/${encodeURIComponent(trimmed)}`, {
    method: 'DELETE',
    signal,
  })

  if (!res.ok) {
    let errorData: ApiErrorData = { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    try {
      errorData = await res.json()
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorData)
  }

  return await res.json()
}

