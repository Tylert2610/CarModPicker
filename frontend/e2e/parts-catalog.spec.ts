import { test, expect, type Route, type Request } from '@playwright/test';

const MULTI_PART_ID = '11111111-1111-1111-1111-111111111111';
const SINGLE_PART_ID = '22222222-2222-2222-2222-222222222222';
const ZERO_PART_ID = '33333333-3333-3333-3333-333333333333';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const FRESH_LISTING_OBSERVED_AT = new Date(
  Date.parse(FIXED_NOW_ISO) - 5 * ONE_DAY_MS
).toISOString();

const MOCK_CATEGORY_ID = 'cat-1';
const MOCK_CATEGORY = {
  id: MOCK_CATEGORY_ID,
  name: 'brakes',
  display_name: 'Brakes',
  description: null,
  icon: null,
  is_active: true,
  sort_order: 0,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

const MOCK_PART_MANUFACTURER_ID = 'pm-1';
const MOCK_PART_MANUFACTURER = {
  id: MOCK_PART_MANUFACTURER_ID,
  name: 'Acme Performance',
  description: null,
  is_active: true,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const MOCK_USER = {
  id: USER_ID,
  username: 'partshopper',
  email: 'partshopper@example.com',
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

const BUILD_LIST_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const MOCK_BUILD_LIST = {
  id: BUILD_LIST_ID,
  name: 'My Build',
  description: 'Demo build list — fixture-only.',
  car_id: null,
  user_id: USER_ID,
  image_urls: null,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

interface MockPart {
  id: string;
  name: string;
  description: string;
  best_price_cents: number | null;
  image_urls: null;
  category_id: string;
  user_id: string;
  car_ids: string[];
  is_universal: boolean;
  part_manufacturer_id: string;
  part_manufacturer: string;
  part_number: string;
  specifications: null;
  canonical_part_id: null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote: null;
}

/**
 * Build a catalog part fixture from the shared defaults plus `overrides`.
 */
function makeMockPart(
  overrides: Partial<MockPart> & Pick<MockPart, 'id' | 'name'>
): MockPart {
  return {
    description: 'Mocked part for e2e parts-catalog spec.',
    best_price_cents: 12999,
    image_urls: null,
    category_id: MOCK_CATEGORY_ID,
    user_id: USER_ID,
    car_ids: [],
    is_universal: true,
    part_manufacturer_id: MOCK_PART_MANUFACTURER_ID,
    part_manufacturer: MOCK_PART_MANUFACTURER.name,
    part_number: 'PN-0001',
    specifications: null,
    canonical_part_id: null,
    is_verified: true,
    source: 'crawler',
    edit_count: 0,
    created_at: FIXED_NOW_ISO,
    updated_at: FIXED_NOW_ISO,
    upvotes: 5,
    downvotes: 1,
    total_votes: 6,
    user_vote: null,
    ...overrides,
  };
}

const MOCK_PARTS: Record<string, MockPart> = {
  [MULTI_PART_ID]: makeMockPart({
    id: MULTI_PART_ID,
    name: 'Multi-Observation Brake Pad',
    part_number: 'MULTI-001',
    best_price_cents: 12999,
  }),
  [SINGLE_PART_ID]: makeMockPart({
    id: SINGLE_PART_ID,
    name: 'Single-Observation Coilover',
    part_number: 'SINGLE-001',
    best_price_cents: 49999,
  }),
  [ZERO_PART_ID]: makeMockPart({
    id: ZERO_PART_ID,
    name: 'Zero-Observation Turbo',
    part_number: 'ZERO-001',
    best_price_cents: null,
  }),
};

const MOCK_PARTS_LIST: MockPart[] = [
  MOCK_PARTS[MULTI_PART_ID],
  MOCK_PARTS[SINGLE_PART_ID],
  MOCK_PARTS[ZERO_PART_ID],
];

const MOCK_PAGINATED_PARTS = {
  data: MOCK_PARTS_LIST,
  pagination: {
    current_page: 1,
    total_pages: 1,
    total_items: MOCK_PARTS_LIST.length,
    items_per_page: 100,
    has_next: false,
    has_previous: false,
  },
};

const MOCK_BATCH_RESPONSE = {
  summaries: {
    [MULTI_PART_ID]: {
      min_cents: 11999,
      max_cents: 14999,
      last_cents: 12999,
      last_observed_at: FRESH_LISTING_OBSERVED_AT,
      trend: 'down',
      observation_count: 6,
    },
    [SINGLE_PART_ID]: {
      min_cents: 49999,
      max_cents: 49999,
      last_cents: 49999,
      last_observed_at: FRESH_LISTING_OBSERVED_AT,
      trend: 'flat',
      observation_count: 1,
    },
    [ZERO_PART_ID]: {
      min_cents: null,
      max_cents: null,
      last_cents: null,
      last_observed_at: null,
      trend: 'flat',
      observation_count: 0,
    },
  },
  window: '90d',
  requested_count: 3,
  found_count: 3,
};

/** PartPriceHistoryReadWithRetailer fixtures for the SparklineCell lazy fetch. */
const MOCK_PRICE_HISTORY_ARRAY = [
  {
    id: 'h1',
    part_listing_id: 'l1',
    price_cents: 14999,
    observed_at: '2026-02-01T00:00:00.000Z',
    retailer_id: 'r1',
    retailer_name: 'RetailerOne',
  },
  {
    id: 'h2',
    part_listing_id: 'l1',
    price_cents: 13999,
    observed_at: '2026-02-15T00:00:00.000Z',
    retailer_id: 'r1',
    retailer_name: 'RetailerOne',
  },
  {
    id: 'h3',
    part_listing_id: 'l1',
    price_cents: 13499,
    observed_at: '2026-03-01T00:00:00.000Z',
    retailer_id: 'r1',
    retailer_name: 'RetailerOne',
  },
  {
    id: 'h4',
    part_listing_id: 'l2',
    price_cents: 12999,
    observed_at: '2026-03-15T00:00:00.000Z',
    retailer_id: 'r2',
    retailer_name: 'RetailerTwo',
  },
  {
    id: 'h5',
    part_listing_id: 'l2',
    price_cents: 12499,
    observed_at: '2026-04-01T00:00:00.000Z',
    retailer_id: 'r2',
    retailer_name: 'RetailerTwo',
  },
  {
    id: 'h6',
    part_listing_id: 'l1',
    price_cents: 11999,
    observed_at: '2026-04-20T00:00:00.000Z',
    retailer_id: 'r1',
    retailer_name: 'RetailerOne',
  },
];

const MOCK_SINGLE_SUMMARY = {
  summary: MOCK_BATCH_RESPONSE.summaries[MULTI_PART_ID],
  retailers: [
    {
      retailer_id: 'r1',
      retailer_name: 'RetailerOne',
      min_cents: 11999,
      max_cents: 14999,
      last_cents: 11999,
      last_observed_at: FRESH_LISTING_OBSERVED_AT,
      observation_count: 4,
    },
  ],
  history: MOCK_PRICE_HISTORY_ARRAY,
  window: '90d',
};

/**
 * Viewport wide enough that the responsive parts table keeps its lowest
 * priority `actions` column, which carries the AddToBuildList trigger.
 */
const VIEWPORT_WIDE_ENOUGH_FOR_ACTIONS_COLUMN = { width: 2400, height: 900 };

const MOCK_VOTE_SUMMARY_DEFAULT = {
  entity_id: '',
  entity_type: 'part',
  upvotes: 0,
  downvotes: 0,
  total_votes: 0,
  vote_score: 0,
  user_vote: null,
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

interface NetworkCounters {
  batchPriceHistoryPostCount: number;
}

/**
 * Serve the parts catalog's API contract from fixtures as an authenticated
 * viewer, counting batch price-history POSTs in `counters` and 404ing the rest.
 *
 * The route matcher excludes Vite source modules at `/src/api/*.ts`.
 */
async function mockApi(
  page: import('@playwright/test').Page,
  counters: NetworkCounters
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

      if (path === '/categories/' && method === 'GET') {
        return jsonResponse(route, [MOCK_CATEGORY]);
      }
      if (path.startsWith('/categories/') && method === 'GET') {
        return jsonResponse(route, MOCK_CATEGORY);
      }
      if (path === '/part-manufacturers/' && method === 'GET') {
        return jsonResponse(route, [MOCK_PART_MANUFACTURER]);
      }
      if (path.startsWith('/part-manufacturers/') && method === 'GET') {
        return jsonResponse(route, MOCK_PART_MANUFACTURER);
      }
      if (path === '/car-generations/by-ids' && method === 'GET') {
        return jsonResponse(route, []);
      }
      if (path === '/car-generations/stats/car-makes' && method === 'GET') {
        return jsonResponse(route, {});
      }
      if (path.startsWith('/car-generations/') && method === 'GET') {
        return jsonResponse(route, []);
      }

      if (path === '/parts/with-votes' && method === 'GET') {
        return jsonResponse(route, MOCK_PAGINATED_PARTS);
      }
      if (path === '/parts/filter-options' && method === 'GET') {
        return jsonResponse(route, {
          category_ids: [MOCK_CATEGORY_ID],
          part_manufacturer_ids: [MOCK_PART_MANUFACTURER_ID],
          car_ids: [],
          make_names: [],
        });
      }

      if (path === '/parts/price-history' && method === 'POST') {
        counters.batchPriceHistoryPostCount += 1;
        return jsonResponse(route, MOCK_BATCH_RESPONSE);
      }

      const priceHistoryMatch = path.match(/^\/parts\/([^/]+)\/price-history$/);
      if (priceHistoryMatch && method === 'GET') {
        const partId = priceHistoryMatch[1];
        if (partId === MULTI_PART_ID) {
          return jsonResponse(route, MOCK_SINGLE_SUMMARY);
        }
        return jsonResponse(route, {
          summary: {
            min_cents: null,
            max_cents: null,
            last_cents: null,
            last_observed_at: null,
            trend: 'flat',
            observation_count: 0,
          },
          retailers: [],
          history: [],
          window: '90d',
        });
      }

      const buildListsByUserMatch = path.match(
        /^\/build-lists\/user\/([^/]+)$/
      );
      if (buildListsByUserMatch && method === 'GET') {
        return jsonResponse(route, [MOCK_BUILD_LIST]);
      }

      const voteSummaryMatch = path.match(
        /^\/votes\/([^/]+)\/([^/]+)\/summary$/
      );
      if (voteSummaryMatch && method === 'GET') {
        const [, entityType, entityId] = voteSummaryMatch;
        return jsonResponse(route, {
          ...MOCK_VOTE_SUMMARY_DEFAULT,
          entity_id: entityId,
          entity_type: entityType,
        });
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
async function setupPage(
  page: import('@playwright/test').Page
): Promise<NetworkCounters> {
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

  const counters: NetworkCounters = { batchPriceHistoryPostCount: 0 };
  await mockApi(page, counters);

  page.on('pageerror', (err) => {
    throw err;
  });

  return counters;
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

test('parts catalog visual regression', async ({ page }) => {
  const counters = await setupPage(page);

  let observedBatchPosts = 0;
  page.on('request', (req: Request) => {
    if (req.method() === 'POST' && req.url().includes('/parts/price-history')) {
      observedBatchPosts += 1;
    }
  });

  await page.goto('/parts');
  await waitForPageReady(page);

  const multiSparkContainer = page
    .locator(`[data-part-id="${MULTI_PART_ID}"]`)
    .first();
  await multiSparkContainer.scrollIntoViewIfNeeded();
  await expect(multiSparkContainer).toBeVisible();
  const multiSparkline = multiSparkContainer.locator('[role="img"]').first();
  await expect(multiSparkline).toBeVisible({ timeout: 10_000 });

  expect(counters.batchPriceHistoryPostCount).toBe(1);
  expect(observedBatchPosts).toBe(1);

  await expect(page).toHaveScreenshot({ fullPage: true });
});

test('add-to-build-list dialog opens, focus moves into it, Escape closes it', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Dialog keyboard interaction is asserted once on desktop'
  );

  await page.setViewportSize(VIEWPORT_WIDE_ENOUGH_FOR_ACTIONS_COLUMN);
  await setupPage(page);

  await page.goto('/parts');
  await waitForPageReady(page);

  const trigger = page
    .getByTestId('parts-catalog-add-to-build-list-trigger')
    .first();
  await expect(trigger).toBeVisible({ timeout: 15_000 });
  await trigger.click();

  const dialog = page.getByTestId('parts-catalog-add-to-build-list-dialog');
  await expect(dialog).toBeVisible();

  const focusInsideDialog = await page.evaluate(() => {
    const dialogEl = document.querySelector(
      '[data-testid="parts-catalog-add-to-build-list-dialog"]'
    );
    const focused = document.activeElement;
    return !!(dialogEl && focused && dialogEl.contains(focused));
  });
  expect(focusInsideDialog).toBe(true);

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('tab traversal lands visible focus on search input', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Tab order is asserted once on desktop'
  );

  await setupPage(page);

  await page.goto('/parts');
  await waitForPageReady(page);

  const searchInput = page.getByTestId('parts-catalog-search');
  await expect(searchInput).toBeVisible();

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
    const isSearch = await page.evaluate(
      () =>
        (document.activeElement as HTMLElement | null)?.dataset.testid ===
        'parts-catalog-search'
    );
    if (isSearch) {
      foundOnTab = i;
      break;
    }
  }

  expect(
    foundOnTab,
    'Tab traversal never reached the parts-catalog search input within 30 presses'
  ).toBeGreaterThan(0);

  const hasFocusRing = await searchInput.evaluate((el) => {
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
