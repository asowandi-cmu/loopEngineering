import { test, expect } from '@playwright/test';

/**
 * E2E coverage for the Trading Journal homepage.
 *
 * Exercises the full add-a-trade path a real user takes: load the page, fill the
 * known ES long trade, confirm the LIVE preview computes the expected P&L before
 * submit, submit, then assert the new table row's Net P&L and that the stats
 * header reflects the trade. This guards the end-to-end contract (island mounts,
 * API round-trips, server-computed P&L renders) that unit tests can't see.
 */
test.describe('Trading Journal', () => {
  test('has the Trading Journal title and mounts the island', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Trading Journal/i);
    await expect(page.locator('[data-island="journal"]')).toBeVisible();
  });

  test('adds a trade: live preview, persisted row, and updated stats', async ({ page }) => {
    await page.goto('/');

    const form = page.locator('form[aria-label="Add trade"]');
    await expect(form).toBeVisible();

    await form.locator('input[name="symbol"]').fill('ES');
    await form.locator('input[name="product_name"]').fill('E-mini S&P 500');
    await form.locator('select[name="side"]').selectOption('long');
    await form.locator('input[name="contracts"]').fill('2');
    await form.locator('input[name="entry_price"]').fill('5000');
    await form.locator('input[name="exit_price"]').fill('5010');
    await form.locator('input[name="tick_size"]').fill('0.25');
    await form.locator('input[name="tick_value"]').fill('12.5');
    await form.locator('input[name="entry_at"]').fill('2026-07-19T13:30');
    await form.locator('input[name="exit_at"]').fill('2026-07-19T14:05');
    await form.locator('input[name="fees"]').fill('4.5');

    // Live preview computes before submit.
    const preview = page.locator('[aria-label="P&L preview"]');
    await expect(preview).toContainText('40');
    await expect(preview).toContainText('995.50');

    await page.screenshot({ path: 'e2e/journal-before-submit.png', fullPage: true });

    await form.getByRole('button', { name: 'Add trade' }).click();

    // The new row appears with the server-computed Net P&L.
    const row = page.locator('[data-testid="trade-row"]').first();
    await expect(row).toBeVisible();
    await expect(row).toContainText('ES');
    await expect(row).toContainText('995.50');

    // Stats header reflects the trade.
    const stats = page.locator('section[aria-label="Summary statistics"]');
    await expect(stats).toContainText('995.50');
    await expect(stats).toContainText('1'); // # Trades

    await page.screenshot({ path: 'e2e/journal-populated.png', fullPage: true });
  });
});
