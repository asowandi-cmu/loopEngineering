import { test, expect } from '@playwright/test';

/**
 * E2E coverage for the Space Invaders homepage.
 *
 * Canvas games are opaque to the DOM, so we verify what's observable: the page
 * shell, the mounted canvas with the engine's fixed dimensions, that input
 * doesn't raise console errors, and that pressing Space advances the game
 * (asserted via a change in the rendered canvas pixels).
 */
test.describe('Space Invaders Page', () => {
  test('has the Space Invaders title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Space Invaders/i);
  });

  test('mounts a visible canvas with the expected dimensions', async ({ page }) => {
    await page.goto('/');

    const island = page.locator('[data-island="game"]');
    await expect(island).toBeVisible();

    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();
    await expect(canvas).toHaveAttribute('width', '800');
    await expect(canvas).toHaveAttribute('height', '600');
  });

  test('arrow keys and space do not produce console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/');
    await expect(page.locator('canvas')).toBeVisible();

    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Space');
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
  });

  test('pressing Space starts the game and changes the canvas', async ({ page }) => {
    await page.goto('/');
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();
    // Let the start screen render at least one frame.
    await page.waitForTimeout(200);

    const before = await canvas.screenshot();

    await page.keyboard.press('Space');
    // Allow the game to enter the playing state and animate a few frames.
    await page.waitForTimeout(500);

    const after = await canvas.screenshot();
    expect(Buffer.compare(before, after)).not.toBe(0);
  });
});
