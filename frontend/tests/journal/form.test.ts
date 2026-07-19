/**
 * Vitest coverage for the form validation helper (`journal/validation.ts`).
 *
 * These assert the client rejects exactly what the backend rejects (tick_size
 * <= 0, contracts < 1, exit before entry, missing exit) and accepts a valid
 * trade — so the form can block bad submits and its messages never contradict
 * the API's.
 */
import { describe, expect, it } from 'vitest'
import { isValid, validateTradeInput } from '@/journal/validation'
import { emptyTradeInput, type TradeInput } from '@/journal/types'

const valid = (over: Partial<TradeInput> = {}): TradeInput => ({
  ...emptyTradeInput(),
  symbol: 'ES',
  side: 'long',
  contracts: '2',
  entry_price: '5000',
  exit_price: '5010',
  tick_size: '0.25',
  tick_value: '12.5',
  entry_at: '2026-07-19T13:30',
  exit_at: '2026-07-19T14:05',
  fees: '4.5',
  ...over,
})

describe('validateTradeInput', () => {
  it('accepts a fully valid trade', () => {
    expect(isValid(validateTradeInput(valid()))).toBe(true)
  })

  it('rejects tick_size = 0', () => {
    expect(validateTradeInput(valid({ tick_size: '0' })).tick_size).toBeDefined()
  })

  it('rejects negative tick_size', () => {
    expect(validateTradeInput(valid({ tick_size: '-0.25' })).tick_size).toBeDefined()
  })

  it('rejects tick_value = 0', () => {
    expect(validateTradeInput(valid({ tick_value: '0' })).tick_value).toBeDefined()
  })

  it('rejects contracts < 1', () => {
    expect(validateTradeInput(valid({ contracts: '0' })).contracts).toBeDefined()
  })

  it('rejects non-integer contracts', () => {
    expect(validateTradeInput(valid({ contracts: '1.5' })).contracts).toBeDefined()
  })

  it('rejects negative entry price', () => {
    expect(validateTradeInput(valid({ entry_price: '-1' })).entry_price).toBeDefined()
  })

  it('rejects a missing exit price', () => {
    expect(validateTradeInput(valid({ exit_price: '' })).exit_price).toBeDefined()
  })

  it('rejects exit time before entry time', () => {
    expect(
      validateTradeInput(valid({ entry_at: '2026-07-19T14:05', exit_at: '2026-07-19T13:30' }))
        .exit_at,
    ).toBeDefined()
  })

  it('rejects an empty symbol', () => {
    expect(validateTradeInput(valid({ symbol: '   ' })).symbol).toBeDefined()
  })

  it('treats empty fees as valid (defaults to 0)', () => {
    expect(validateTradeInput(valid({ fees: '' })).fees).toBeUndefined()
  })
})
