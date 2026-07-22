/**
 * Vitest coverage for the sync API wrappers (`journal/sync.ts`).
 *
 * These assert the three things a wrapper bug would silently break: the status
 * poll parses the server shape, `importCsv` sends a real multipart body (a JSON
 * content-type here would corrupt the upload), and a non-2xx response surfaces as
 * `ApiRequestError` so the panel can show the server's message.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  connect,
  connectTestAccount,
  getSyncStatus,
  importCsv,
  saveCredentials,
} from '@/journal/sync'
import { ApiRequestError } from '@/journal/api'
import type { SyncStatus } from '@/journal/types'

interface MockResponse {
  ok?: boolean
  status?: number
  body?: unknown
}

function mockFetch(response: MockResponse) {
  const fn = vi.fn().mockResolvedValue({
    ok: response.ok ?? true,
    status: response.status ?? 200,
    json: async () => response.body ?? {},
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

const sampleStatus: SyncStatus = {
  enabled: true,
  status: 'streaming',
  credentials_configured: true,
  last_synced_at: '2026-07-21T14:05:00Z',
  last_fill_at: '2026-07-21T14:04:58Z',
  last_error: null,
  counts: { trades_dxtrade: 12, fills: 40, needs_review: 1 },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('getSyncStatus', () => {
  it('GETs /api/sync/status and parses the status shape', async () => {
    const fetchMock = mockFetch({ body: sampleStatus })
    const status = await getSyncStatus()
    expect(fetchMock).toHaveBeenCalledWith('/api/sync/status', expect.anything())
    expect(status.status).toBe('streaming')
    expect(status.counts.trades_dxtrade).toBe(12)
  })
})

describe('importCsv', () => {
  it('POSTs a multipart FormData body without a JSON content-type', async () => {
    const fetchMock = mockFetch({ body: { created: 1, skipped_duplicates: 0 } })
    const file = new File(['symbol,side\nES,buy'], 'statement.csv', { type: 'text/csv' })
    await importCsv(file)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/sync/import')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBeInstanceOf(File)
    // Critical: the browser must set multipart Content-Type + boundary itself.
    expect(init.headers).not.toHaveProperty('Content-Type')
  })
})

describe('saveCredentials', () => {
  it('POSTs JSON credentials and resolves undefined on 204', async () => {
    const fetchMock = mockFetch({ status: 204 })
    const result = await saveCredentials({ username: 'u', password: 'p', domain: 'd' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/sync/credentials')
    expect(JSON.parse(init.body as string)).toMatchObject({ username: 'u', domain: 'd' })
    expect(result).toBeUndefined()
  })
})

describe('connectTestAccount', () => {
  it('POSTs /api/sync/demo and parses the status + ingest result', async () => {
    const fetchMock = mockFetch({
      body: { status: sampleStatus, result: { created: 3, open_positions: 1, skipped_duplicates: 0 } },
    })
    const { status, result } = await connectTestAccount()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/sync/demo')
    expect(init.method).toBe('POST')
    expect(status.status).toBe('streaming')
    expect(result.created).toBe(3)
  })
})

describe('error surfacing', () => {
  it('rejects with ApiRequestError carrying the server message', async () => {
    mockFetch({ ok: false, status: 400, body: { message: 'DXtrade credentials are not configured' } })
    await expect(connect()).rejects.toBeInstanceOf(ApiRequestError)
    await expect(connect()).rejects.toThrow('DXtrade credentials are not configured')
  })
})
