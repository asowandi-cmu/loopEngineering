import { test, expect } from '@playwright/test';

/**
 * E2E coverage for the Phase 2 automated (DXtrade) sync flow.
 *
 * Drives the real reconciliation pipeline through the guarded test-ingest
 * endpoint (no live broker): POST a fixture fill batch, then assert the journal
 * picks up the synced trade *live* (status polling triggers a refetch) with a
 * `dxtrade` "Auto" source badge and the correct server-computed Net P&L. Re-POST
 * the identical batch and assert the row count is unchanged and the pipeline
 * reports `skipped_duplicates > 0` — this is Phase 2's core promise: reconnects /
 * replays never create duplicate trades. The Phase 1 manual spec
 * (`journal.spec.ts`) still passes independently.
 *
 * The ES round-trip below (buy 2 @ 5000, sell 2 @ 5010, $2.25 fee/side) is the
 * same trade as the manual E2E: 40 ticks × $12.50 × 2 − $4.50 = $995.50 net.
 */
const FILLS = [
  {
    external_exec_id: 'E2E-SYNC-1',
    external_order_id: 'E2E-O1',
    account: 'E2E',
    symbol: 'ES',
    action: 'buy',
    quantity: 2,
    price: '5000.00',
    fee: '2.25',
    executed_at: '2026-07-20T13:30:00Z',
  },
  {
    external_exec_id: 'E2E-SYNC-2',
    external_order_id: 'E2E-O2',
    account: 'E2E',
    symbol: 'ES',
    action: 'sell',
    quantity: 2,
    price: '5010.00',
    fee: '2.25',
    executed_at: '2026-07-20T13:45:00Z',
  },
];

async function ingest(request: import('@playwright/test').APIRequestContext, fills: unknown[]) {
  const response = await request.post('/api/sync/_test/ingest', { data: fills });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{
    created: number;
    skipped_duplicates: number;
  }>;
}

test.describe('Trading Journal — DXtrade sync', () => {
  test('ingests a fill batch: live dxtrade badge, Net P&L, and dedupe on replay', async ({
    page,
  }) => {
    await page.goto('/');
    await expect(page.locator('[data-island="journal"]')).toBeVisible();

    // First ingest: the pipeline creates exactly one round-trip trade.
    const first = await ingest(page.request, FILLS);
    expect(first.created).toBe(1);

    // The status poll (5s) refetches trades; the synced row appears with an
    // "Auto" source badge and the server-computed Net P&L — no manual reload.
    const row = page
      .locator('[data-testid="trade-row"]')
      .filter({ hasText: 'E2E-SYNC' })
      .or(page.locator('[data-testid="trade-row"]').filter({ has: page.locator('[data-source="dxtrade"]') }))
      .first();
    await expect(row).toBeVisible({ timeout: 15000 });
    await expect(row).toContainText('ES');
    await expect(row.locator('[data-testid="source-badge"]')).toContainText('Auto');
    await expect(row).toContainText('995.50');

    // Stats header reflects the synced trade's P&L (live update).
    const stats = page.locator('section[aria-label="Summary statistics"]');
    await expect(stats).toContainText('995.50');

    await page.screenshot({ path: 'e2e/journal-sync-populated.png', fullPage: true });

    const rowCountAfterFirst = await page.locator('[data-testid="trade-row"]').count();

    // Re-ingest the identical batch: idempotent — zero new trades, dupes skipped.
    const second = await ingest(page.request, FILLS);
    expect(second.created).toBe(0);
    expect(second.skipped_duplicates).toBeGreaterThan(0);

    // Give the poll a cycle, then confirm the row count did not grow.
    await page.waitForTimeout(6000);
    const rowCountAfterSecond = await page.locator('[data-testid="trade-row"]').count();
    expect(rowCountAfterSecond).toBe(rowCountAfterFirst);
  });
});
