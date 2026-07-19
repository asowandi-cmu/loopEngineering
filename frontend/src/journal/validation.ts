/**
 * Client-side form validation mirroring the backend Pydantic rules.
 *
 * Returning a `field -> message` map (rather than a boolean) lets `TradeForm`
 * render inline messages and disable submit while invalid — catching bad input
 * before a round-trip. The backend remains authoritative; this is UX only, and
 * its messages intentionally echo the API's so the two never contradict.
 */
import type { TradeInput } from './types'

export type FieldErrors = Partial<Record<keyof TradeInput, string>>

function parseNumber(raw: string): number {
  return raw.trim() === '' ? NaN : Number(raw)
}

export function validateTradeInput(input: TradeInput): FieldErrors {
  const errors: FieldErrors = {}

  if (input.symbol.trim() === '') {
    errors.symbol = 'must not be empty'
  } else if (input.symbol.trim().length > 16) {
    errors.symbol = 'must be at most 16 characters'
  }

  if (input.side !== 'long' && input.side !== 'short') {
    errors.side = "must be 'long' or 'short'"
  }

  const contracts = parseNumber(input.contracts)
  if (!Number.isInteger(contracts) || contracts < 1) {
    errors.contracts = 'must be at least 1'
  }

  const entryPrice = parseNumber(input.entry_price)
  if (!Number.isFinite(entryPrice)) {
    errors.entry_price = 'required'
  } else if (entryPrice < 0) {
    errors.entry_price = 'must be greater than or equal to 0'
  }

  const exitPrice = parseNumber(input.exit_price)
  if (!Number.isFinite(exitPrice)) {
    errors.exit_price = 'required'
  } else if (exitPrice < 0) {
    errors.exit_price = 'must be greater than or equal to 0'
  }

  const tickSize = parseNumber(input.tick_size)
  if (!Number.isFinite(tickSize) || tickSize <= 0) {
    errors.tick_size = 'must be greater than 0'
  }

  const tickValue = parseNumber(input.tick_value)
  if (!Number.isFinite(tickValue) || tickValue <= 0) {
    errors.tick_value = 'must be greater than 0'
  }

  if (input.fees.trim() !== '') {
    const fees = parseNumber(input.fees)
    if (!Number.isFinite(fees) || fees < 0) {
      errors.fees = 'must be greater than or equal to 0'
    }
  }

  if (input.entry_at.trim() === '') {
    errors.entry_at = 'required'
  }
  if (input.exit_at.trim() === '') {
    errors.exit_at = 'required'
  }
  if (
    input.entry_at.trim() !== '' &&
    input.exit_at.trim() !== '' &&
    input.exit_at < input.entry_at
  ) {
    errors.exit_at = 'must be at or after entry time'
  }

  return errors
}

export function isValid(errors: FieldErrors): boolean {
  return Object.keys(errors).length === 0
}
