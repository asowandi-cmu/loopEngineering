/**
 * JournalIsland — the state owner for the Trading Journal.
 *
 * Fetches trades + stats on mount, holds them (plus edit/loading/error state),
 * and after every mutation refetches both. Refetch-after-mutation is the
 * simplest correct approach: the server owns the derived P&L and the aggregate
 * stats, so re-reading guarantees the header and table always reflect the true
 * persisted state rather than an optimistic client guess.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Stats, SyncStatus, Trade, TradeInput } from '@/journal/types'
import {
  createTrade,
  deleteTrade,
  getStats,
  listTrades,
  updateTrade,
} from '@/journal/api'
import { getSyncStatus } from '@/journal/sync'
import { ConnectionPanel } from './ConnectionPanel'
import { StatsHeader } from './StatsHeader'
import { TradeForm } from './TradeForm'
import { TradeTable } from './TradeTable'

/** How often to poll `/api/sync/status` so streamed trades appear live. */
const SYNC_POLL_MS = 5000

export function JournalIsland() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)

  // Last-seen sync watermark; a growth in either field means new synced trades
  // landed, so we refetch. `null` until the first poll (so mount doesn't refetch).
  const syncWatermark = useRef<{ trades: number; lastFill: string | null } | null>(null)

  const refetch = useCallback(async (): Promise<void> => {
    const [nextTrades, nextStats] = await Promise.all([listTrades(), getStats()])
    setTrades(nextTrades)
    setStats(nextStats)
  }, [])

  // Record a fresh status without triggering the poll's growth-refetch (used by
  // connect/disconnect and after an import, where the parent refetches directly).
  const rememberStatus = useCallback((status: SyncStatus): void => {
    setSyncStatus(status)
    syncWatermark.current = {
      trades: status.counts.trades_dxtrade,
      lastFill: status.last_fill_at,
    }
  }, [])

  // After an import/reconcile: reload trades + stats, then refresh the status pill.
  const handleSyncDataChanged = useCallback(async (): Promise<void> => {
    await refetch()
    try {
      rememberStatus(await getSyncStatus())
    } catch {
      /* transient — the next poll will reconcile the pill */
    }
  }, [refetch, rememberStatus])

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

  // Poll sync status; refetch trades + stats whenever the watermark grows so
  // streamed trades appear live without a manual reload (Phase 2 live update).
  useEffect(() => {
    let active = true

    const tick = async (): Promise<void> => {
      try {
        const status = await getSyncStatus()
        if (!active) return
        setSyncStatus(status)
        const prev = syncWatermark.current
        const grew =
          prev !== null &&
          (status.counts.trades_dxtrade > prev.trades ||
            (status.last_fill_at !== null && status.last_fill_at !== prev.lastFill))
        syncWatermark.current = {
          trades: status.counts.trades_dxtrade,
          lastFill: status.last_fill_at,
        }
        if (grew) await refetch()
      } catch {
        /* ignore transient poll errors; the next tick retries */
      }
    }

    void tick()
    const timer = window.setInterval(() => void tick(), SYNC_POLL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [refetch])

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
      <ConnectionPanel
        status={syncStatus}
        onStatusChange={rememberStatus}
        onDataChanged={handleSyncDataChanged}
      />

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
