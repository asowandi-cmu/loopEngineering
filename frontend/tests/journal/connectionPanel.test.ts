/**
 * Vitest coverage for the ConnectionPanel state logic.
 *
 * The panel's user-facing correctness reduces to two pure derivations: the right
 * pill label for each connection status, and the dedupe summary wording that tells
 * the user Phase 2's idempotent ingest actually skipped duplicates. Testing the
 * exported helpers keeps these assertions render-free and stable.
 */
import { describe, expect, it } from 'vitest'
import { formatDedupe, statusMeta } from '@/islands/journal/ConnectionPanel'
import type { ImportResult } from '@/journal/types'

describe('statusMeta', () => {
  it('labels streaming as connected', () => {
    expect(statusMeta('streaming').label).toBe('Connected · streaming')
  })

  it('labels connecting with a pulsing amber pill', () => {
    const meta = statusMeta('connecting')
    expect(meta.label).toBe('Connecting…')
    expect(meta.className).toContain('animate-pulse')
  })

  it('labels error', () => {
    expect(statusMeta('error').label).toBe('Error')
  })

  it('labels disconnected', () => {
    expect(statusMeta('disconnected').label).toBe('Disconnected')
  })

  it('falls back to disconnected for an unknown status', () => {
    expect(statusMeta('bogus').label).toBe('Disconnected')
  })
})

describe('formatDedupe', () => {
  it('formats the imported / skipped / flagged summary', () => {
    const result: ImportResult = {
      created: 2,
      updated: 0,
      skipped_duplicates: 1,
      flagged: 3,
      open_positions: 0,
    }
    expect(formatDedupe(result)).toBe(
      '2 imported · 1 skipped as duplicates · 3 flagged for review',
    )
  })
})
