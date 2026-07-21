/**
 * Typed fetch wrappers for the Trading Journal JSON API.
 *
 * Every wrapper throws `ApiRequestError` on a non-2xx response, exposing the
 * parsed `{ message, fields }` so `TradeForm` can surface backend 400 validation
 * errors inline (the same field->message contract the server emits).
 */
import type { Stats, Trade, TradeInput } from './types'

export class ApiRequestError extends Error {
  fields: Record<string, string>

  constructor(message: string, fields: Record<string, string>) {
    super(message)
    this.name = 'ApiRequestError'
    this.fields = fields
  }
}

interface ErrorBody {
  message?: string
  fields?: Record<string, string>
}

export async function request<T>(url: string, init?: Parameters<typeof fetch>[1]): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    ...init,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const data: unknown = await response.json().catch(() => ({}))

  if (!response.ok) {
    const body = (data ?? {}) as ErrorBody
    throw new ApiRequestError(body.message ?? 'Request failed', body.fields ?? {})
  }

  return data as T
}

/** Convert raw form state into a JSON request body for the API. */
function toBody(input: TradeInput): Record<string, unknown> {
  const optional = (value: string): string | null => {
    const trimmed = value.trim()
    return trimmed === '' ? null : trimmed
  }
  return {
    symbol: input.symbol.trim(),
    product_name: optional(input.product_name),
    side: input.side,
    contracts: Number(input.contracts),
    entry_price: Number(input.entry_price),
    exit_price: Number(input.exit_price),
    tick_size: Number(input.tick_size),
    tick_value: Number(input.tick_value),
    entry_at: input.entry_at,
    exit_at: input.exit_at,
    fees: input.fees.trim() === '' ? 0 : Number(input.fees),
    strategy: optional(input.strategy),
    notes: optional(input.notes),
  }
}

export function listTrades(): Promise<Trade[]> {
  return request<{ trades: Trade[] }>('/api/trades').then((r) => r.trades)
}

export function getStats(): Promise<Stats> {
  return request<Stats>('/api/trades/stats')
}

export function createTrade(input: TradeInput): Promise<Trade> {
  return request<Trade>('/api/trades', {
    method: 'POST',
    body: JSON.stringify(toBody(input)),
  })
}

export function updateTrade(id: number, input: TradeInput): Promise<Trade> {
  return request<Trade>(`/api/trades/${id}`, {
    method: 'PUT',
    body: JSON.stringify(toBody(input)),
  })
}

export function deleteTrade(id: number): Promise<void> {
  return request<void>(`/api/trades/${id}`, { method: 'DELETE' })
}
