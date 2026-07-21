/**
 * Shared TypeScript types for the Trading Journal island.
 *
 * `Trade` and `Stats` mirror the backend JSON API response shapes; `TradeInput`
 * is the raw controlled-form state (all numeric fields are strings while the
 * user types, `side` is a select). Keeping these in one place lets the pure
 * `pnl.ts`/`validation.ts` helpers and the React components agree on shapes.
 */

export type Side = 'long' | 'short'

/** A persisted trade as returned by the JSON API (includes derived P&L). */
export interface Trade {
  id: number
  symbol: string
  product_name: string | null
  side: Side
  contracts: number
  entry_price: number
  exit_price: number
  tick_size: number
  tick_value: number
  entry_at: string
  exit_at: string
  fees: number
  ticks: number
  gross_pnl: number
  net_pnl: number
  strategy: string | null
  notes: string | null
  // Phase 2 provenance/dedupe fields. Manual trades read 'manual'/null/'ok'/null;
  // synced trades read 'dxtrade' and may carry an external_id + review flag.
  source: 'manual' | 'dxtrade'
  external_id: string | null
  review_status: string
  duplicate_of: number | null
  created_at: string
  updated_at: string
}

/** Summary statistics from `GET /api/trades/stats`. */
export interface Stats {
  num_trades: number
  total_net_pnl: number
  total_gross_pnl: number
  total_fees: number
  total_ticks: number
  wins: number
  losses: number
  scratches: number
  win_rate: number
  average_win: number
  average_loss: number
}

/** One of the four observed connection states the sync worker reports. */
export type SyncConnectionStatus = 'disconnected' | 'connecting' | 'streaming' | 'error'

/** Live headline counts shown next to the status pill. */
export interface SyncCounts {
  trades_dxtrade: number
  fills: number
  needs_review: number
}

/**
 * Observed sync state from `GET /api/sync/status`. Deliberately secret-free —
 * the server exposes only whether credentials are configured, never their value.
 */
export interface SyncStatus {
  enabled: boolean
  status: SyncConnectionStatus
  credentials_configured: boolean
  last_synced_at: string | null
  last_fill_at: string | null
  last_error: string | null
  counts: SyncCounts
}

/**
 * Dedupe-visible counts returned by import / reconcile / test-ingest. `created`
 * is new trades; `skipped_duplicates` are fills already ingested; `flagged` need
 * review (unknown spec or a possible manual duplicate).
 */
export interface ImportResult {
  created: number
  updated: number
  skipped_duplicates: number
  flagged: number
  open_positions: number
}

/** Raw add/edit form state — numeric fields are strings while editing. */
export interface TradeInput {
  symbol: string
  product_name: string
  side: Side
  contracts: string
  entry_price: string
  exit_price: string
  tick_size: string
  tick_value: string
  entry_at: string
  exit_at: string
  fees: string
  strategy: string
  notes: string
}

/** A blank form in add mode. */
export function emptyTradeInput(): TradeInput {
  return {
    symbol: '',
    product_name: '',
    side: 'long',
    contracts: '1',
    entry_price: '',
    exit_price: '',
    tick_size: '',
    tick_value: '',
    entry_at: '',
    exit_at: '',
    fees: '0',
    strategy: '',
    notes: '',
  }
}
