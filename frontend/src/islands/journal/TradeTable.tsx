/**
 * TradeTable — the editable/deletable list of persisted trades.
 *
 * Renders the authoritative server-computed columns (including ticks and P&L) so
 * the table never re-derives values. Edit loads the row back into `TradeForm`;
 * Delete confirms first (destructive). Shows an explicit empty state so a fresh
 * journal reads intentionally rather than looking broken.
 */
import type { ReactNode } from 'react'
import type { Trade } from '@/journal/types'
import { formatMoney, formatTicks, pnlColor } from '@/journal/format'
import { SourceBadge } from './SourceBadge'

interface TradeTableProps {
  trades: Trade[]
  onEdit: (trade: Trade) => void
  onDelete: (trade: Trade) => void
}

function formatDateTime(iso: string): string {
  return iso.slice(0, 16).replace('T', ' ')
}

export function TradeTable({ trades, onEdit, onDelete }: TradeTableProps) {
  if (trades.length === 0) {
    return (
      <p className="text-gray-500 text-center py-10">
        No trades yet — add your first trade above.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
        <thead className="bg-gray-100 text-gray-600 text-left">
          <tr>
            <Th>Symbol</Th>
            <Th>Source</Th>
            <Th>Side</Th>
            <Th className="text-right">Contracts</Th>
            <Th className="text-right">Entry</Th>
            <Th className="text-right">Exit</Th>
            <Th className="text-right">Tick Size</Th>
            <Th className="text-right">Tick Value</Th>
            <Th className="text-right">Ticks</Th>
            <Th className="text-right">Gross P&L</Th>
            <Th className="text-right">Net P&L</Th>
            <Th>Entry / Exit</Th>
            <Th>Strategy</Th>
            <Th className="text-right">Actions</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {trades.map((trade) => (
            <tr key={trade.id} data-testid="trade-row" className="hover:bg-gray-50">
              <Td className="font-medium text-gray-800">{trade.symbol}</Td>
              <Td>
                <SourceBadge
                  source={trade.source}
                  reviewStatus={trade.review_status}
                  duplicateOf={trade.duplicate_of}
                />
              </Td>
              <Td>{trade.side}</Td>
              <Td className="text-right">{trade.contracts}</Td>
              <Td className="text-right">{trade.entry_price}</Td>
              <Td className="text-right">{trade.exit_price}</Td>
              <Td className="text-right">{trade.tick_size}</Td>
              <Td className="text-right">{trade.tick_value}</Td>
              <Td className={`text-right ${pnlColor(trade.ticks)}`}>
                {formatTicks(trade.ticks)}
              </Td>
              <Td className={`text-right ${pnlColor(trade.gross_pnl)}`}>
                {formatMoney(trade.gross_pnl)}
              </Td>
              <Td className={`text-right font-semibold ${pnlColor(trade.net_pnl)}`}>
                {formatMoney(trade.net_pnl)}
              </Td>
              <Td className="whitespace-nowrap text-xs text-gray-500">
                {formatDateTime(trade.entry_at)}
                <br />
                {formatDateTime(trade.exit_at)}
              </Td>
              <Td className="text-gray-600">{trade.strategy ?? '—'}</Td>
              <Td className="text-right whitespace-nowrap">
                <button
                  type="button"
                  onClick={() => onEdit(trade)}
                  className="text-blue-600 hover:underline mr-3"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(trade)}
                  className="text-red-600 hover:underline"
                >
                  Delete
                </button>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface CellProps {
  children: ReactNode
  className?: string
}

function Th({ children, className = '' }: CellProps) {
  return <th className={`px-3 py-2 font-medium ${className}`}>{children}</th>
}

function Td({ children, className = '' }: CellProps) {
  return <td className={`px-3 py-2 ${className}`}>{children}</td>
}
