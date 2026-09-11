import { test, expect, type Route, type Request } from '@playwright/test';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const SEVEN_DAYS_AGO_ISO = new Date(
  Date.parse(FIXED_NOW_ISO) - 7 * ONE_DAY_MS
).toISOString();

const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

/** Admin user fixture; `is_admin` satisfies the dashboard's access check. */
const MOCK_ADMIN_USER = {
  id: USER_ID,
  username: 'admintester',
  email: 'admintester@example.com',
  disabled: false,
  email_verified: true,
  image_urls: null,
  is_superuser: false,
  is_admin: true,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'inactive',
  totp_enabled: false,
};

/**
 * ExtractionHealthResponse fixture. The empty browser tier and the 1.0 failure
 * rate are deliberate, so the empty-summary and full-ratio paths both render.
 */
const MOCK_EXTRACTION_HEALTH = {
  compliance: {
    compliant: 108,
    total: 108,
    per_tier: {
      http: '83/83',
      tls: '15/15',
      browser: '10/10',
    },
  },
  coverage: {
    per_tier: {
      http: {
        parts_with_specs: 4200,
        parts_total: 9000,
        per_field: {
          weight_grams: 0.42,
          material: 0.18,
          dimensions_mm: 0.31,
        },
      },
      tls: {
        parts_with_specs: 1100,
        parts_total: 2400,
        per_field: {
          weight_grams: 0.55,
          material: 0.22,
        },
      },
      browser: {
        parts_with_specs: 0,
        parts_total: 0,
        per_field: {
          weight_grams: 0,
          material: 0,
        },
      },
    },
  },
  failure_rate_7d: [
    {
      adapter: 'amazon_browser',
      failed: 12,
      parsed: 12,
      rate: 1.0,
      tier: 'browser',
    },
    {
      adapter: 'rockauto_http',
      failed: 5,
      parsed: 95,
      rate: 0.05,
      tier: 'http',
    },
    {
      adapter: 'tirerack_tls',
      failed: 0,
      parsed: 80,
      rate: 0.0,
      tier: 'tls',
    },
  ],
  window: {
    days: 7,
    since: SEVEN_DAYS_AGO_ISO,
  },
};

/**
 * Fulfil a mocked route with a JSON body.
 */
function jsonResponse(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

/**
 * Serve the admin pages' API contract from fixtures, 404ing anything else.
 *
 * The route matcher excludes Vite source modules at `/src/api/*.ts`.
 */
async function mockApi(page: import('@playwright/test').Page): Promise<void> {
  await page.route(
    /\/api\/(?!.*\.ts)/,
    async (route: Route, request: Request) => {
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();

      if (path === '/users/me' && method === 'GET') {
        return jsonResponse(route, MOCK_ADMIN_USER);
      }
      if (path === '/app-settings/' && method === 'GET') {
        return jsonResponse(route, {
          premium_disabled: true,
          updated_at: FIXED_NOW_ISO,
        });
      }

      if (
        (path === '/admin/extraction-health' ||
          path === '/admin/extraction-health/') &&
        method === 'GET'
      ) {
        return jsonResponse(route, MOCK_EXTRACTION_HEALTH);
      }

      if (path.startsWith('/admin/') && method === 'GET') {
        return jsonResponse(route, {});
      }

      return jsonResponse(
        route,
        { detail: `Mock miss: ${method} ${path}` },
        404
      );
    }
  );
}

/**
 * Install the API mocks, pin the clock, and suppress the consent and promo
 * overlays so snapshots are deterministic on every viewport.
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

  await mockApi(page);

  page.on('pageerror', (err) => {
    throw err;
  });
}

/**
 * Wait for the network, fonts, and a short settle window before snapshotting.
 */
async function waitForPageReady(
  page: import('@playwright/test').Page
): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

test('admin dashboard visual regression', async ({ page }) => {
  await setupPage(page);

  await page.goto('/admin');
  await waitForPageReady(page);

  await expect(
    page.getByRole('heading', { name: 'Extraction Health' })
  ).toBeVisible();

  await expect(page).toHaveScreenshot('admin-dashboard-1.png', {
    fullPage: true,
  });
});

test('admin extraction-health visual regression', async ({ page }) => {
  await setupPage(page);

  await page.goto('/admin/extraction-health');
  await waitForPageReady(page);

  await expect(page.getByTestId('compliance-pill-http')).toBeVisible();
  await expect(page.getByTestId('compliance-pill-tls')).toBeVisible();
  await expect(page.getByTestId('compliance-pill-browser')).toBeVisible();
  await expect(page.getByTestId('failure-rate-table')).toBeVisible();

  await expect(page).toHaveScreenshot('admin-extraction-health-1.png', {
    fullPage: true,
  });
});

test('extraction-health: keyboard Tab lands visible focus on a control', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Keyboard focus is asserted once on desktop'
  );

  await setupPage(page);

  await page.goto('/admin/extraction-health');
  await waitForPageReady(page);

  await expect(
    page.getByRole('button', { name: /Refresh extraction health/i })
  ).toBeVisible();

  await page.evaluate(() => {
    document.body.focus();
    if (document.activeElement !== document.body) {
      document.body.setAttribute('tabindex', '-1');
      document.body.focus();
    }
  });

  await page.keyboard.press('Tab');

  const focused = page.locator(':focus');
  await expect(focused).toBeVisible();

  const focusRingPresent = await focused.evaluate((el) => {
    const cls = el.className;
    if (typeof cls === 'string' && cls.includes('ring')) {
      return true;
    }
    if (!el.matches(':focus-visible')) {
      return false;
    }
    const styles = window.getComputedStyle(el);
    const outline = styles.outlineStyle;
    const boxShadow = styles.boxShadow;
    return (
      (outline !== 'none' && outline !== '') ||
      (boxShadow !== 'none' && boxShadow !== '')
    );
  });
  expect(focusRingPresent).toBe(true);
});
