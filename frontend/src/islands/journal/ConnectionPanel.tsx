/**
 * ConnectionPanel — the DXtrade sync control surface, rendered above the stats
 * header inside the journal island.
 *
 * It owns three responsibilities the user needs to run the automated pipeline:
 * a live **status pill** (disconnected / connecting / streaming / error), a
 * **write-only credentials form** (the password is never pre-filled — the server
 * never returns it, so the field always starts blank), and the **Connect /
 * Disconnect / Import CSV / Reconcile** actions. Every import/reconcile shows a
 * **dedupe summary** ("N imported · M skipped as duplicates · K flagged"), which
 * is the whole point of Phase 2's idempotent ingest: the user can re-run an
 * import and see that no duplicate trades were created.
 *
 * The panel is a controlled child: `JournalIsland` owns `syncStatus` (it polls),
 * passes it down, and receives `onStatusChange` (connect/disconnect returns fresh
 * status) and `onDataChanged` (after an import/reconcile the parent refetches
 * trades + stats so the new rows appear immediately).
 */
import { useCallback, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent, ReactNode } from 'react'
import type { ImportResult, SyncConnectionStatus, SyncStatus } from '@/journal/types'
import {
  connect,
  disconnect,
  importCsv,
  reconcile,
  saveCredentials,
  type CredentialsInput,
} from '@/journal/sync'
import { ApiRequestError } from '@/journal/api'

interface ConnectionPanelProps {
  status: SyncStatus | null
  onStatusChange: (status: SyncStatus) => void
  onDataChanged: () => void | Promise<void>
}

interface StatusMeta {
  label: string
  className: string
  dotClassName: string
}

/**
 * Pure status→pill mapping (exported for unit tests). Kept separate from the
 * component so the "right badge label per status" assertion needs no render.
 */
export function statusMeta(status: SyncConnectionStatus | string): StatusMeta {
  switch (status) {
    case 'streaming':
      return {
        label: 'Connected · streaming',
        className: 'bg-green-100 text-green-700',
        dotClassName: 'bg-green-500',
      }
    case 'connecting':
      return {
        label: 'Connecting…',
        className: 'bg-amber-100 text-amber-700 animate-pulse',
        dotClassName: 'bg-amber-500',
      }
    case 'error':
      return {
        label: 'Error',
        className: 'bg-red-100 text-red-700',
        dotClassName: 'bg-red-500',
      }
    default:
      return {
        label: 'Disconnected',
        className: 'bg-gray-100 text-gray-600',
        dotClassName: 'bg-gray-400',
      }
  }
}

/** Pure dedupe-summary formatter (exported for unit tests). */
export function formatDedupe(result: ImportResult): string {
  return (
    `${result.created} imported · ${result.skipped_duplicates} skipped as duplicates · ` +
    `${result.flagged} flagged for review`
  )
}

const EMPTY_CREDENTIALS: CredentialsInput = {
  username: '',
  password: '',
  domain: '',
  base_url: '',
  ws_url: '',
}

export function ConnectionPanel({ status, onStatusChange, onDataChanged }: ConnectionPanelProps) {
  const [credentials, setCredentials] = useState<CredentialsInput>(EMPTY_CREDENTIALS)
  const [busy, setBusy] = useState<'connect' | 'creds' | 'import' | 'reconcile' | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [credsSaved, setCredsSaved] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const configured = status?.credentials_configured ?? false
  const enabled = status?.enabled ?? false
  const meta = statusMeta(status?.status ?? 'disconnected')

  // Any action clears the last error first; failures surface the API message.
  const run = useCallback(
    async (which: NonNullable<typeof busy>, action: () => Promise<void>): Promise<void> => {
      setBusy(which)
      setError(null)
      try {
        await action()
      } catch (err) {
        setError(err instanceof ApiRequestError ? err.message : 'Something went wrong.')
      } finally {
        setBusy(null)
      }
    },
    [],
  )

  const handleField = (field: keyof CredentialsInput) =>
    (event: ChangeEvent<HTMLInputElement>): void => {
      setCredentials((prev) => ({ ...prev, [field]: event.target.value }))
    }

  const handleSaveCredentials = (event: FormEvent): void => {
    event.preventDefault()
    void run('creds', async () => {
      await saveCredentials({
        username: credentials.username,
        password: credentials.password,
        domain: credentials.domain,
        base_url: credentials.base_url?.trim() || undefined,
        ws_url: credentials.ws_url?.trim() || undefined,
      })
      // Never keep the password around after a successful save.
      setCredentials((prev) => ({ ...prev, password: '' }))
      setCredsSaved(true)
      await onDataChanged()
    })
  }

  const handleToggleConnection = (): void => {
    void run('connect', async () => {
      const next = enabled ? await disconnect() : await connect()
      onStatusChange(next)
    })
  }

  const handleImport = (event: ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0]
    if (!file) return
    void run('import', async () => {
      const imported = await importCsv(file)
      setResult(imported)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await onDataChanged()
    })
  }

  const handleReconcile = (): void => {
    void run('reconcile', async () => {
      setResult(await reconcile())
      await onDataChanged()
    })
  }

  return (
    <section
      aria-label="Broker sync"
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-gray-700">DXtrade Sync</h2>
          <span
            aria-label="Connection status"
            data-testid="sync-status-pill"
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${meta.className}`}
          >
            <span className={`h-2 w-2 rounded-full ${meta.dotClassName}`} />
            {meta.label}
          </span>
          {status?.status === 'error' && status.last_error && (
            <span className="text-xs text-red-600">{status.last_error}</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleToggleConnection}
            disabled={!configured || busy === 'connect'}
            className={`rounded px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${
              enabled ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
            }`}
            title={configured ? '' : 'Configure credentials first'}
          >
            {enabled ? 'Disconnect' : 'Connect'}
          </button>
          <button
            type="button"
            onClick={handleReconcile}
            disabled={busy === 'reconcile'}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Reconcile
          </button>
          <label className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 cursor-pointer">
            Import CSV
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={handleImport}
              className="hidden"
              aria-label="Import statement CSV"
            />
          </label>
        </div>
      </div>

      <form
        aria-label="DXtrade credentials"
        onSubmit={handleSaveCredentials}
        className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end"
      >
        <Field label="Username">
          <input
            name="username"
            value={credentials.username}
            onChange={handleField('username')}
            autoComplete="username"
            className={inputClass}
          />
        </Field>
        <Field label="Password">
          <input
            name="password"
            type="password"
            value={credentials.password}
            onChange={handleField('password')}
            autoComplete="new-password"
            placeholder={configured ? '•••••••• (unchanged)' : ''}
            className={inputClass}
          />
        </Field>
        <Field label="Domain">
          <input
            name="domain"
            value={credentials.domain}
            onChange={handleField('domain')}
            className={inputClass}
          />
        </Field>
        <Field label="Base URL (optional)">
          <input
            name="base_url"
            value={credentials.base_url ?? ''}
            onChange={handleField('base_url')}
            className={inputClass}
          />
        </Field>
        <Field label="WS URL (optional)">
          <input
            name="ws_url"
            value={credentials.ws_url ?? ''}
            onChange={handleField('ws_url')}
            className={inputClass}
          />
        </Field>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy === 'creds'}
            className="rounded bg-gray-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-900 disabled:opacity-50"
          >
            Save credentials
          </button>
          {configured && (
            <span className="text-xs text-green-600" data-testid="creds-configured">
              Credentials configured ✓
            </span>
          )}
        </div>
      </form>

      {credsSaved && !configured && (
        <p className="mt-3 text-xs text-gray-500">Credentials saved.</p>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      {result && (
        <p className="mt-3 text-sm text-gray-700" data-testid="dedupe-summary">
          {formatDedupe(result)}
          {result.open_positions > 0 && ` · ${result.open_positions} open (no trade yet)`}
        </p>
      )}
    </section>
  )
}

const inputClass =
  'w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-500">{label}</span>
      {children}
    </label>
  )
}
