/**
 * Typed fetch wrappers for the Phase 2 sync API (`/api/sync/*`).
 *
 * These reuse `api.ts`'s `request`/`ApiRequestError` so the sync surface shares
 * the exact same non-2xx → `ApiRequestError({ message, fields })` contract as the
 * Phase 1 trade API (the connection panel surfaces those messages inline).
 *
 * Two things are load-bearing here:
 * - **`importCsv` sends multipart**: it builds a `FormData` and passes only an
 *   `Accept` header, so the browser sets `Content-Type: multipart/form-data` with
 *   the correct boundary. Setting a JSON content-type would corrupt the upload.
 * - **Credentials are write-only**: `saveCredentials` POSTs and the server replies
 *   204 with no body; the password is never read back by any wrapper here.
 */
import { request } from './api'
import type { ImportResult, SyncStatus } from './types'

/** Write-only DXtrade credentials posted by the connection panel. */
export interface CredentialsInput {
  username: string
  password: string
  domain: string
  base_url?: string
  ws_url?: string
}

/** Poll the observed sync state (status pill + live counts). */
export function getSyncStatus(): Promise<SyncStatus> {
  return request<SyncStatus>('/api/sync/status')
}

/** Set desired state `enabled=true`; rejects (400) if credentials are missing. */
export function connect(): Promise<SyncStatus> {
  return request<SyncStatus>('/api/sync/connect', { method: 'POST' })
}

/** Set desired state `enabled=false` (the worker performs the clean disconnect). */
export function disconnect(): Promise<SyncStatus> {
  return request<SyncStatus>('/api/sync/disconnect', { method: 'POST' })
}

/** Persist write-only credentials to the server's gitignored secret store (204). */
export function saveCredentials(credentials: CredentialsInput): Promise<void> {
  return request<void>('/api/sync/credentials', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

/** Import a statement CSV via multipart upload (browser sets the boundary). */
export function importCsv(file: File): Promise<ImportResult> {
  const body = new FormData()
  body.append('file', file)
  return request<ImportResult>('/api/sync/import', {
    method: 'POST',
    body,
    // Only Accept — let the browser set multipart Content-Type + boundary.
    headers: { Accept: 'application/json' },
  })
}

/** Re-derive every trade from stored fills (backfill / after a spec fix). */
export function reconcile(): Promise<ImportResult> {
  return request<ImportResult>('/api/sync/reconcile', { method: 'POST' })
}

/**
 * Drive the real ingest pipeline with a posted fixture-fill batch.
 *
 * Only wired to a live route when the backend runs with TESTING/DEBUG (the route
 * 404s in production); used by the automated E2E to exercise the sync flow with
 * no live broker.
 */
export function testIngest(fills: unknown[]): Promise<ImportResult> {
  return request<ImportResult>('/api/sync/_test/ingest', {
    method: 'POST',
    body: JSON.stringify(fills),
  })
}
