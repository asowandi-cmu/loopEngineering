/**
 * StatsHeader — the summary-statistics row at the top of the journal.
 *
 * Renders server-computed aggregates (Total Net P&L colored by sign, Win Rate,
 * # Trades, Avg Win, Avg Loss, Total Ticks). Numbers only — charting is Phase 2.
 * Shows zeros for an empty journal (the API returns all-zero stats, never an
 * error), so no special empty-state branch is needed.
 */
import type { Stats } from '@/journal/types'
import { formatMoney, formatPercent, formatTicks, pnlColor } from '@/journal/format'

interface StatsHeaderProps {
  stats: Stats | null
}

interface TileProps {
  label: string
  value: string
  valueClass?: string
}

function Tile({ label, value, valueClass = 'text-gray-800' }: TileProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`text-xl font-semibold ${valueClass}`}>{value}</div>
    </div>
  )
}

export function StatsHeader({ stats }: StatsHeaderProps) {
  const s: Stats = stats ?? {
    num_trades: 0,
    total_net_pnl: 0,
    total_gross_pnl: 0,
    total_fees: 0,
    total_ticks: 0,
    wins: 0,
    losses: 0,
    scratches: 0,
    win_rate: 0,
    average_win: 0,
    average_loss: 0,
  }

  return (
    <section
      aria-label="Summary statistics"
      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8"
    >
      <Tile
        label="Total Net P&L"
        value={formatMoney(s.total_net_pnl)}
        valueClass={pnlColor(s.total_net_pnl)}
      />
      <Tile label="Win Rate" value={formatPercent(s.win_rate)} />
      <Tile label="# Trades" value={String(s.num_trades)} />
      <Tile
        label="Avg Win"
        value={formatMoney(s.average_win)}
        valueClass={pnlColor(s.average_win)}
      />
      <Tile
        label="Avg Loss"
        value={formatMoney(s.average_loss)}
        valueClass={pnlColor(s.average_loss)}
      />
      <Tile
        label="Total Ticks"
        value={formatTicks(s.total_ticks)}
        valueClass={pnlColor(s.total_ticks)}
      />
    </section>
  )
}
