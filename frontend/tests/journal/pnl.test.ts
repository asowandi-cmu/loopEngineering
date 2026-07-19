/**
 * Vitest coverage for the pure P&L preview helper (`journal/pnl.ts`).
 *
 * These pin the frontend preview to the SAME results the backend `compute_pnl`
 * produces, so the "identical backend/frontend math" acceptance criterion can't
 * silently regress. Covers long/short sign flip, multi-contract, fees, fractional
 * ticks, and the divide-by-zero guard (`tickSize <= 0 -> null`).
 */
import { describe, expect, it } from 'vitest'
import {
  computeGrossPnl,
  computeNetPnl,
  computePreview,
  computeTicks,
} from '@/journal/pnl'
import type { PnlInput } from '@/journal/pnl'

const es = (over: Partial<PnlInput> = {}): PnlInput => ({
  side: 'long',
  contracts: 2,
  entryPrice: 5000,
  exitPrice: 5010,
  tickSize: 0.25,
  tickValue: 12.5,
  fees: 4.5,
  ...over,
})

describe('computeTicks', () => {
  it('long: per-contract signed ticks gained', () => {
    expect(computeTicks(5000, 5010, 0.25, 'long')).toBe(40)
  })

  it('short: sign flips vs price move', () => {
    expect(computeTicks(5010, 5000, 0.25, 'short')).toBe(40)
    expect(computeTicks(5000, 5010, 0.25, 'short')).toBe(-40)
  })

  it('returns null when tickSize <= 0 (divide-by-zero guard)', () => {
    expect(computeTicks(5000, 5010, 0, 'long')).toBeNull()
    expect(computeTicks(5000, 5010, -0.25, 'long')).toBeNull()
  })

  it('returns null for non-finite prices', () => {
    expect(computeTicks(NaN, 5010, 0.25, 'long')).toBeNull()
  })
})

describe('computeGrossPnl / computeNetPnl', () => {
  it('multiplier applies to dollars only', () => {
    expect(computeGrossPnl(40, 12.5, 2)).toBe(1000)
    expect(computeNetPnl(1000, 4.5)).toBe(995.5)
  })
})

describe('computePreview', () => {
  it('matches the canonical ES long example (995.5 net)', () => {
    expect(computePreview(es())).toEqual({ ticks: 40, grossPnl: 1000, netPnl: 995.5 })
  })

  it('short equivalent matches the long', () => {
    const result = computePreview(es({ side: 'short', entryPrice: 5010, exitPrice: 5000 }))
    expect(result).toEqual({ ticks: 40, grossPnl: 1000, netPnl: 995.5 })
  })

  it('handles fractional ticks (CL 0.01 / $10, 1.5 ticks)', () => {
    // The preview is display-only float math (the backend's Decimal is
    // authoritative), so assert with tolerance against binary-float noise.
    const result = computePreview(
      es({ entryPrice: 75, exitPrice: 75.015, tickSize: 0.01, tickValue: 10, contracts: 1, fees: 0 }),
    )
    expect(result?.ticks).toBeCloseTo(1.5, 6)
    expect(result?.grossPnl).toBeCloseTo(15, 6)
    expect(result?.netPnl).toBeCloseTo(15, 6)
  })

  it('fees greater than gross yield a negative net', () => {
    const result = computePreview(es({ contracts: 1, fees: 600 }))
    expect(result?.grossPnl).toBe(500)
    expect(result?.netPnl).toBe(-100)
  })

  it('returns null when tickSize is zero', () => {
    expect(computePreview(es({ tickSize: 0 }))).toBeNull()
  })

  it('returns null when contracts < 1', () => {
    expect(computePreview(es({ contracts: 0 }))).toBeNull()
  })

  it('returns null when a price is missing (NaN)', () => {
    expect(computePreview(es({ exitPrice: NaN }))).toBeNull()
  })
})
