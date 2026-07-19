/**
 * TradeForm — the add/edit form with a live client-side P&L preview.
 *
 * The preview recomputes on every keystroke via the pure `computePreview`
 * (the same tick formula the backend uses), so the trader sees ticks/gross/net
 * before submitting; it shows "—" until inputs are complete and valid. Client
 * validation mirrors the backend and disables submit while invalid, and any
 * backend 400 `fields` are surfaced inline so the two error sources agree.
 * The same component serves add and edit modes (pre-filled from a selected row).
 */
import { useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import type { Trade, TradeInput } from '@/journal/types'
import { emptyTradeInput } from '@/journal/types'
import { computePreview } from '@/journal/pnl'
import { formatMoney, formatTicks, pnlColor } from '@/journal/format'
import {
  FieldErrors,
  isValid,
  validateTradeInput,
} from '@/journal/validation'
import { ApiRequestError } from '@/journal/api'

interface TradeFormProps {
  editingTrade: Trade | null
  onSubmit: (input: TradeInput) => Promise<void>
  onCancelEdit: () => void
}

/** Datetime-local inputs want "YYYY-MM-DDTHH:MM"; trim ISO seconds/zone. */
function toLocalInput(iso: string): string {
  return iso.slice(0, 16)
}

function tradeToInput(trade: Trade): TradeInput {
  return {
    symbol: trade.symbol,
    product_name: trade.product_name ?? '',
    side: trade.side,
    contracts: String(trade.contracts),
    entry_price: String(trade.entry_price),
    exit_price: String(trade.exit_price),
    tick_size: String(trade.tick_size),
    tick_value: String(trade.tick_value),
    entry_at: toLocalInput(trade.entry_at),
    exit_at: toLocalInput(trade.exit_at),
    fees: String(trade.fees),
    strategy: trade.strategy ?? '',
    notes: trade.notes ?? '',
  }
}

function parseMaybe(raw: string): number {
  return raw.trim() === '' ? NaN : Number(raw)
}

export function TradeForm({ editingTrade, onSubmit, onCancelEdit }: TradeFormProps) {
  const [input, setInput] = useState<TradeInput>(emptyTradeInput)
  const [serverErrors, setServerErrors] = useState<FieldErrors>({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setInput(editingTrade ? tradeToInput(editingTrade) : emptyTradeInput())
    setServerErrors({})
  }, [editingTrade])

  const clientErrors = useMemo(() => validateTradeInput(input), [input])

  const preview = useMemo(
    () =>
      computePreview({
        side: input.side,
        contracts: parseMaybe(input.contracts),
        entryPrice: parseMaybe(input.entry_price),
        exitPrice: parseMaybe(input.exit_price),
        tickSize: parseMaybe(input.tick_size),
        tickValue: parseMaybe(input.tick_value),
        fees: input.fees.trim() === '' ? 0 : parseMaybe(input.fees),
      }),
    [input],
  )

  const errorFor = (field: keyof TradeInput): string | undefined =>
    clientErrors[field] ?? serverErrors[field]

  const setField = (field: keyof TradeInput, value: string): void => {
    setInput((prev) => ({ ...prev, [field]: value }))
    setServerErrors((prev) => {
      if (!(field in prev)) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }

  const handleSubmit = async (event: FormEvent): Promise<void> => {
    event.preventDefault()
    if (!isValid(clientErrors) || submitting) return
    setSubmitting(true)
    try {
      await onSubmit(input)
      if (!editingTrade) setInput(emptyTradeInput())
      setServerErrors({})
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setServerErrors(err.fields as FieldErrors)
      } else {
        setServerErrors({ symbol: 'Something went wrong. Please try again.' })
      }
    } finally {
      setSubmitting(false)
    }
  }

  const editing = editingTrade !== null

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={editing ? 'Edit trade' : 'Add trade'}
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-8"
    >
      <h2 className="text-lg font-semibold mb-4 text-gray-800">
        {editing ? `Edit trade #${editingTrade.id}` : 'Add a trade'}
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Field label="Symbol" error={errorFor('symbol')}>
          <input
            type="text"
            name="symbol"
            value={input.symbol}
            onChange={(e) => setField('symbol', e.target.value)}
            placeholder="ES"
            className={inputClass}
          />
        </Field>

        <Field label="Product name" error={errorFor('product_name')}>
          <input
            type="text"
            name="product_name"
            value={input.product_name}
            onChange={(e) => setField('product_name', e.target.value)}
            placeholder="E-mini S&P 500"
            className={inputClass}
          />
        </Field>

        <Field label="Side" error={errorFor('side')}>
          <select
            name="side"
            value={input.side}
            onChange={(e) => setField('side', e.target.value)}
            className={inputClass}
          >
            <option value="long">long</option>
            <option value="short">short</option>
          </select>
        </Field>

        <Field label="Contracts" error={errorFor('contracts')}>
          <input
            type="number"
            min="1"
            step="1"
            name="contracts"
            value={input.contracts}
            onChange={(e) => setField('contracts', e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Entry price" error={errorFor('entry_price')}>
          <input
            type="number"
            step="any"
            name="entry_price"
            value={input.entry_price}
            onChange={(e) => setField('entry_price', e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Exit price" error={errorFor('exit_price')}>
          <input
            type="number"
            step="any"
            name="exit_price"
            value={input.exit_price}
            onChange={(e) => setField('exit_price', e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Tick size" error={errorFor('tick_size')}>
          <input
            type="number"
            step="any"
            name="tick_size"
            value={input.tick_size}
            onChange={(e) => setField('tick_size', e.target.value)}
            placeholder="0.25"
            className={inputClass}
          />
        </Field>

        <Field label="Tick value ($)" error={errorFor('tick_value')}>
          <input
            type="number"
            step="any"
            name="tick_value"
            value={input.tick_value}
            onChange={(e) => setField('tick_value', e.target.value)}
            placeholder="12.50"
            className={inputClass}
          />
        </Field>

        <Field label="Entry time" error={errorFor('entry_at')}>
          <input
            type="datetime-local"
            name="entry_at"
            value={input.entry_at}
            onChange={(e) => setField('entry_at', e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Exit time" error={errorFor('exit_at')}>
          <input
            type="datetime-local"
            name="exit_at"
            value={input.exit_at}
            onChange={(e) => setField('exit_at', e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Fees ($)" error={errorFor('fees')}>
          <input
            type="number"
            step="any"
            name="fees"
            value={input.fees}
            onChange={(e) => setField('fees', e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Strategy" error={errorFor('strategy')}>
          <input
            type="text"
            name="strategy"
            value={input.strategy}
            onChange={(e) => setField('strategy', e.target.value)}
            placeholder="ORB"
            className={inputClass}
          />
        </Field>
      </div>

      <div className="mt-4">
        <label className="block text-xs uppercase tracking-wide text-gray-500 mb-1">
          Notes
        </label>
        <textarea
          name="notes"
            value={input.notes}
          onChange={(e) => setField('notes', e.target.value)}
          rows={2}
          className={inputClass}
        />
      </div>

      {/* Live P&L preview */}
      <div
        aria-label="P&L preview"
        className="mt-5 flex flex-wrap gap-6 items-center bg-gray-50 rounded-md px-4 py-3"
      >
        <PreviewStat label="Ticks" value={preview ? formatTicks(preview.ticks) : '—'} />
        <PreviewStat
          label="Gross P&L"
          value={preview ? formatMoney(preview.grossPnl) : '—'}
          valueClass={preview ? pnlColor(preview.grossPnl) : undefined}
        />
        <PreviewStat
          label="Net P&L"
          value={preview ? formatMoney(preview.netPnl) : '—'}
          valueClass={preview ? pnlColor(preview.netPnl) : undefined}
        />
      </div>

      <div className="mt-5 flex gap-3">
        <button
          type="submit"
          disabled={!isValid(clientErrors) || submitting}
          className="px-4 py-2 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {editing ? 'Save changes' : 'Add trade'}
        </button>
        {editing && (
          <button
            type="button"
            onClick={onCancelEdit}
            className="px-4 py-2 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100"
          >
            Cancel edit
          </button>
        )}
      </div>
    </form>
  )
}

const inputClass =
  'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'

interface FieldProps {
  label: string
  error?: string
  children: ReactNode
}

function Field({ label, error, children }: FieldProps) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wide text-gray-500 mb-1">
        {label}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

interface PreviewStatProps {
  label: string
  value: string
  valueClass?: string
}

function PreviewStat({ label, value, valueClass = 'text-gray-800' }: PreviewStatProps) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`text-lg font-semibold ${valueClass}`}>{value}</div>
    </div>
  )
}
