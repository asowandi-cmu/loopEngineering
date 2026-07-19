/**
 * Pure, framework-free P&L helpers for the live form preview.
 *
 * This mirrors the backend's single source of truth (`controllers/trade.py:
 * compute_pnl`) EXACTLY — same tick convention: `ticks` is per-contract signed
 * movement, and the contract multiplier applies to dollars only. It is used only
 * for the prospective single-trade preview; the persisted stats come from the
 * server. Guards divide-by-zero (`tickSize <= 0` -> null) and incomplete input
 * (any non-finite number -> null) so the UI can show "—".
 */
import type { Side } from './types'

export interface PnlInput {
  side: Side
  contracts: number
  entryPrice: number
  exitPrice: number
  tickSize: number
  tickValue: number
  fees: number
}

export interface PnlResult {
  ticks: number
  grossPnl: number
  netPnl: number
}

/**
 * Per-contract signed ticks gained. Returns null when `tickSize <= 0` (guards
 * divide-by-zero, matching the backend rejection) or prices are not finite.
 */
export function computeTicks(
  entryPrice: number,
  exitPrice: number,
  tickSize: number,
  side: Side,
): number | null {
  if (!Number.isFinite(tickSize) || tickSize <= 0) return null
  if (!Number.isFinite(entryPrice) || !Number.isFinite(exitPrice)) return null
  const direction = side === 'long' ? 1 : -1
  return ((exitPrice - entryPrice) / tickSize) * direction
}

/** Gross dollar P&L before fees: `ticks * tickValue * contracts`. */
export function computeGrossPnl(
  ticks: number,
  tickValue: number,
  contracts: number,
): number {
  return ticks * tickValue * contracts
}

/** Net dollar P&L: `grossPnl - fees`. */
export function computeNetPnl(grossPnl: number, fees: number): number {
  return grossPnl - fees
}

/**
 * Compute the full `{ ticks, grossPnl, netPnl }` preview for a prospective
 * trade, or null when any input is missing/invalid so the caller shows "—".
 */
export function computePreview(input: PnlInput): PnlResult | null {
  const { side, contracts, entryPrice, exitPrice, tickSize, tickValue, fees } = input

  const ticks = computeTicks(entryPrice, exitPrice, tickSize, side)
  if (ticks === null) return null
  if (!Number.isFinite(contracts) || contracts < 1) return null
  if (!Number.isFinite(tickValue) || tickValue <= 0) return null

  const safeFees = Number.isFinite(fees) ? fees : 0
  const grossPnl = computeGrossPnl(ticks, tickValue, contracts)
  const netPnl = computeNetPnl(grossPnl, safeFees)
  return { ticks, grossPnl, netPnl }
}
