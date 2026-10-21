import { ApiError } from '../types/api'
import type { AnalysisResponse, ApiErrorData, StockLookupItem } from '../types/api'

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
