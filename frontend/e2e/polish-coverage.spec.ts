import { test, expect } from '@playwright/test';

import { ALL_ROUTES } from '../src/test/route-coverage-list';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';

/**
 * Convert a route path into a stable, readable snapshot filename slug.
 */
function slugForRoute(path: string): string {
  if (path === '/') return 'root';
  return path
    .replace(/^\//, '')
    .replace(/\//g, '-')
    .replace(/[^a-zA-Z0-9-]/g, '_');
}

/**
 * Pin the clock and suppress the consent and promo overlays so fullPage
 * baselines stay deterministic across runs and viewports.
 */
async function setupPage(page: import('@playwright/test').Page): Promise<void> {
  await page.addInitScript((nowIso: string) => {
    const fixed = new Date(nowIso).getTime();
    const realNow = Date.now.bind(Date);
    Date.now = () => fixed;
    (globalThis as unknown as Record<string, unknown>).__REAL_DATE_NOW__ =
      realNow;
  }, FIXED_NOW_ISO);

  await page.addInitScript(() => {
    try {
      localStorage.setItem('cookie_consent_v1', 'accepted');
      const today = new Date();
      const y = today.getFullYear();
      const m = String(today.getMonth() + 1).padStart(2, '0');
      const d = String(today.getDate()).padStart(2, '0');
      localStorage.setItem(
        'chrome_extension_promo_last_dismissed',
        `${y}-${m}-${d}`
      );
    } catch {
      return;
    }
  });
}

/**
 * Wait for the visual surface to settle, falling back to a fixed window on
 * routes that poll and never reach networkidle.
 */
async function waitForPageReady(
  page: import('@playwright/test').Page
): Promise<void> {
  try {
    await page.waitForLoadState('networkidle', { timeout: 8000 });
  } catch {
    await page.waitForLoadState('domcontentloaded');
  }
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

for (const { path } of ALL_ROUTES) {
  const slug = slugForRoute(path);

  test(`polish-coverage: ${path}`, async ({ page }) => {
    await setupPage(page);

    page.on('pageerror', (err) => {
      throw err;
    });

    await page.goto(path);
    await waitForPageReady(page);

    await expect(page).toHaveScreenshot(`${slug}.png`, {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });
}
