import { ApiError } from '../types/api'
import type { ApiErrorData } from '../types/api'

export interface NightlyPlanItem {
  item_id?: number
  plan_id: string
  stock_id: string
  stock_name: string
  market: string
  strategy: string
  win_rate: number
  trade_count: number
  entry_price: number
  stop_loss: number
  take_profit: number
  holding_days: number
  risk_reward_ratio: number
  close_price: number
  volume: number
  reason?: string
}

export interface SchedulerStatus {
  running: boolean
  next_run_time: string | null
  cron: string
}

export interface NightlyPlanResponse {
  found: boolean
  plan_id: string | null
  scan_date: string
  created_at: string | null
  status: string
  total_candidates: number
  selected_count: number
  notes: string | null
  items: NightlyPlanItem[]
  scheduler_status?: SchedulerStatus
}

export interface TriggerNightlyScanResponse {
  status: string
  plan_id?: string
  scan_date?: string
  selected_count?: number
  total_candidates?: number
  plan?: any
  error?: string
  reason?: string
}

export async function fetchNightlyPlan(
  date?: string,
  signal?: AbortSignal
): Promise<NightlyPlanResponse> {
  const query = date ? `?date=${encodeURIComponent(date)}` : ''
  const res = await fetch(`/api/scanner/nightly-plan${query}`, { signal })

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

export async function triggerNightlyPlan(
  date?: string,
  signal?: AbortSignal
): Promise<TriggerNightlyScanResponse> {
  const body = date ? JSON.stringify({ scan_date: date }) : JSON.stringify({})
  const res = await fetch('/api/scanner/nightly-plan/trigger', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
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
