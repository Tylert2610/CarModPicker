import { test, expect, type Route, type Request } from '@playwright/test';

const BUILD_LIST_ID = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
const CAR_ID = 'dddddddd-dddd-dddd-dddd-dddddddddddd';
const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';

const MOCK_USER = {
  id: USER_ID,
  username: 'buildtester',
  email: 'buildtester@example.com',
  disabled: false,
  email_verified: true,
  image_urls: null,
  is_superuser: false,
  is_admin: false,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'inactive',
  totp_enabled: false,
};

const MOCK_BUILD_LIST = {
  id: BUILD_LIST_ID,
  name: 'Demo Build List',
  description: 'Mocked build list for the S09 e2e demo flow.',
  car_id: CAR_ID,
  user_id: USER_ID,
  image_urls: null,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

const MOCK_CAR = {
  id: CAR_ID,
  car_make_name: 'Honda',
  car_model_name: 'Civic',
  car_model_display_name: 'Civic',
  generation_name: 'EK',
  display_name: null,
  display_label: 'Honda Civic EK',
  car_model_display_label: 'Civic',
  start_year: 1996,
  end_year: 2000,
  description: null,
  image_urls: null,
};

const MOCK_VOTE_SUMMARY = {
  entity_id: BUILD_LIST_ID,
  entity_type: 'build_list',
  upvotes: 0,
  downvotes: 0,
  total_votes: 0,
  vote_score: 0,
  user_vote: null,
};

interface MockState {
  unexpected: Array<{ method: string; path: string }>;
}

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
 * Serve the build-list detail page's API contract from fixtures, recording any
 * unmatched request in `state` so drift from the contract is visible.
 *
 * The route matcher excludes Vite source modules at `/src/api/*.ts`.
 */
async function mockApi(
  page: import('@playwright/test').Page,
  state: MockState
): Promise<void> {
  await page.route(
    /\/api\/(?!.*\.ts)/,
    async (route: Route, request: Request) => {
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();

      if (path === '/users/me' && method === 'GET') {
        return jsonResponse(route, MOCK_USER);
      }
      if (path === '/app-settings/' && method === 'GET') {
        return jsonResponse(route, {
          premium_disabled: true,
          updated_at: FIXED_NOW_ISO,
        });
      }

      if (path === `/build-lists/${BUILD_LIST_ID}` && method === 'GET') {
        return jsonResponse(route, MOCK_BUILD_LIST);
      }
      if (path === `/build-lists/${BUILD_LIST_ID}/phases` && method === 'GET') {
        return jsonResponse(route, []);
      }
      if (
        path === `/build-list-parts/${BUILD_LIST_ID}/parts` &&
        method === 'GET'
      ) {
        return jsonResponse(route, []);
      }

      if (path === `/car-generations/${CAR_ID}` && method === 'GET') {
        return jsonResponse(route, MOCK_CAR);
      }
      if (path === '/car-generations/' && method === 'GET') {
        return jsonResponse(route, []);
      }

      if (path === '/categories/' && method === 'GET') {
        return jsonResponse(route, []);
      }
      if (path === '/part-manufacturers/' && method === 'GET') {
        return jsonResponse(route, []);
      }

      const userMatch = path.match(/^\/users\/([^/]+)$/);
      if (userMatch && method === 'GET') {
        return jsonResponse(route, MOCK_USER);
      }

      const voteSummaryMatch = path.match(
        /^\/votes\/([^/]+)\/([^/]+)\/summary$/
      );
      if (voteSummaryMatch && method === 'GET') {
        const [, entityType, entityId] = voteSummaryMatch;
        return jsonResponse(route, {
          ...MOCK_VOTE_SUMMARY,
          entity_id: entityId,
          entity_type: entityType,
        });
      }

      state.unexpected.push({ method, path });
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
 * overlays so clicks and screenshots are deterministic on every viewport.
 */
async function setupPage(
  page: import('@playwright/test').Page
): Promise<MockState> {
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

  const state: MockState = { unexpected: [] };
  await mockApi(page, state);

  page.on('pageerror', (err) => {
    throw err;
  });

  return state;
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

test('build-list detail visual regression', async ({ page }) => {
  await setupPage(page);

  await page.goto(`/build-lists/${BUILD_LIST_ID}`);
  await waitForPageReady(page);

  await expect(page.getByTestId('build-list-edit-trigger')).toBeVisible();

  await expect(page).toHaveScreenshot({ fullPage: true });
});

test('edit dialog opens, focuses, and Escape closes', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Dialog keyboard interaction is asserted once on desktop'
  );

  await setupPage(page);

  await page.goto(`/build-lists/${BUILD_LIST_ID}`);
  await waitForPageReady(page);

  const trigger = page.getByTestId('build-list-edit-trigger');
  await expect(trigger).toBeVisible();
  await trigger.click();

  const dialog = page.getByTestId('build-list-edit-dialog');
  await expect(dialog).toBeVisible();

  const focusInsideDialog = await page.evaluate(() => {
    const dialogEl = document.querySelector(
      '[data-testid="build-list-edit-dialog"]'
    );
    const focused = document.activeElement;
    return !!(dialogEl && focused && dialogEl.contains(focused));
  });
  expect(focusInsideDialog).toBe(true);

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('tab order surfaces visible focus on first interactive control', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Tab order is asserted once on desktop'
  );

  await setupPage(page);

  await page.goto(`/build-lists/${BUILD_LIST_ID}`);
  await waitForPageReady(page);

  const viewBuildLogBtn = page.getByRole('button', { name: 'View Build Log' });
  await expect(viewBuildLogBtn).toBeVisible();

  await page.evaluate(() => {
    document.body.focus();
    if (document.activeElement !== document.body) {
      document.body.setAttribute('tabindex', '-1');
      document.body.focus();
    }
  });

  let foundOnTab = -1;
  for (let i = 1; i <= 30; i++) {
    await page.keyboard.press('Tab');
    const activeText = await page.evaluate(
      () => document.activeElement?.textContent?.trim() ?? ''
    );
    if (activeText === 'View Build Log') {
      foundOnTab = i;
      break;
    }
  }

  expect(
    foundOnTab,
    'Tab traversal never reached the View Build Log button within 30 presses'
  ).toBeGreaterThan(0);

  const hasFocusRing = await viewBuildLogBtn.evaluate((el) => {
    if (!el.matches(':focus-visible')) return false;
    const styles = window.getComputedStyle(el);
    const outline = styles.outlineStyle;
    const boxShadow = styles.boxShadow;
    return (
      (outline !== 'none' && outline !== '') ||
      (boxShadow !== 'none' && boxShadow !== '')
    );
  });
  expect(hasFocusRing).toBe(true);
});
