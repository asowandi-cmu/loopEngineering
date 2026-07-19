/**
 * JournalIsland — the state owner for the Trading Journal.
 *
 * Fetches trades + stats on mount, holds them (plus edit/loading/error state),
 * and after every mutation refetches both. Refetch-after-mutation is the
 * simplest correct approach: the server owns the derived P&L and the aggregate
 * stats, so re-reading guarantees the header and table always reflect the true
 * persisted state rather than an optimistic client guess.
 */
import { useCallback, useEffect, useState } from 'react'
import type { Stats, Trade, TradeInput } from '@/journal/types'
import {
  createTrade,
  deleteTrade,
  getStats,
  listTrades,
  updateTrade,
} from '@/journal/api'
import { StatsHeader } from './StatsHeader'
import { TradeForm } from './TradeForm'
import { TradeTable } from './TradeTable'

export function JournalIsland() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async (): Promise<void> => {
    const [nextTrades, nextStats] = await Promise.all([listTrades(), getStats()])
    setTrades(nextTrades)
    setStats(nextStats)
  }, [])

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const [nextTrades, nextStats] = await Promise.all([listTrades(), getStats()])
        if (!active) return
        setTrades(nextTrades)
        setStats(nextStats)
      } catch {
        if (active) setError('Failed to load trades.')
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const editingTrade = editingId === null
    ? null
    : trades.find((t) => t.id === editingId) ?? null

  const handleSubmit = useCallback(
    async (input: TradeInput): Promise<void> => {
      // Errors (incl. API 400 fields) propagate to TradeForm to display inline.
      if (editingId === null) {
        await createTrade(input)
      } else {
        await updateTrade(editingId, input)
      }
      setEditingId(null)
      await refetch()
    },
    [editingId, refetch],
  )

  const handleEdit = useCallback((trade: Trade): void => {
    setEditingId(trade.id)
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [])

  const handleCancelEdit = useCallback((): void => {
    setEditingId(null)
  }, [])

  const handleDelete = useCallback(
    async (trade: Trade): Promise<void> => {
      const ok =
        typeof window === 'undefined' ||
        window.confirm(`Delete the ${trade.symbol} trade?`)
      if (!ok) return
      await deleteTrade(trade.id)
      if (editingId === trade.id) setEditingId(null)
      await refetch()
    },
    [editingId, refetch],
  )

  return (
    <div>
      <StatsHeader stats={stats} />

      <TradeForm
        editingTrade={editingTrade}
        onSubmit={handleSubmit}
        onCancelEdit={handleCancelEdit}
      />

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {loading ? (
        <p className="text-gray-500 text-center py-10">Loading trades…</p>
      ) : (
        <TradeTable
          trades={trades}
          onEdit={handleEdit}
          onDelete={(trade) => {
            void handleDelete(trade)
          }}
        />
      )}
    </div>
  )
}
