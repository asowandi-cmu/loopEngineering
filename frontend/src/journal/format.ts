/** Small display formatters shared by the journal components. */

/** Format a dollar amount with 2 decimals and a leading sign, e.g. "+995.50". */
export function formatMoney(value: number): string {
  const sign = value < 0 ? '-' : ''
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

/** Format ticks: up to 4 decimals, trailing zeros trimmed (40, 1.5, -40). */
export function formatTicks(value: number): string {
  return Number(value.toFixed(4)).toString()
}

/** Format a 0..1 rate as a percentage, e.g. 0.6667 -> "66.7%". */
export function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

/** Tailwind text color for a P&L value: green positive, red negative. */
export function pnlColor(value: number): string {
  if (value > 0) return 'text-green-600'
  if (value < 0) return 'text-red-600'
  return 'text-gray-600'
}
