import { test, expect, type Route, type Request } from '@playwright/test';

const MULTI_PART_ID = '11111111-1111-1111-1111-111111111111';
const SINGLE_PART_ID = '22222222-2222-2222-2222-222222222222';
const ZERO_PART_ID = '33333333-3333-3333-3333-333333333333';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const FRESH_LISTING_OBSERVED_AT = new Date(
  Date.parse(FIXED_NOW_ISO) - 5 * ONE_DAY_MS
).toISOString();
const STALE_LISTING_OBSERVED_AT = new Date(
  Date.parse(FIXED_NOW_ISO) - 90 * ONE_DAY_MS
).toISOString();
const STALE_LISTING_LOCAL_DATE = new Date(
  STALE_LISTING_OBSERVED_AT
).toLocaleDateString();

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

const SERVICE_USER_ID = 'svc-1';
const MOCK_SERVICE_USER = {
  id: SERVICE_USER_ID,
  username: 'crawler',
  email: 'crawler@example.com',
  disabled: false,
  email_verified: true,
  image_urls: null,
  is_superuser: false,
  is_admin: false,
  is_service_account: true,
  subscription_tier: 'free',
  subscription_status: 'inactive',
  totp_enabled: false,
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

function makeMockPart(
  overrides: Partial<MockPart> & Pick<MockPart, 'id' | 'name'>
): MockPart {
  return {
    description: 'Mocked part for e2e price-history spec.',
    best_price_cents: 12999,
    image_urls: null,
    category_id: MOCK_CATEGORY_ID,
    user_id: SERVICE_USER_ID,
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

/**
 * PartPriceHistoryReadWithRetailer fixtures, served to the SparklineCell lazy
 * fetch and to the legacy detail-page chart.
 */
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
    {
      retailer_id: 'r2',
      retailer_name: 'RetailerTwo',
      min_cents: 12499,
      max_cents: 12999,
      last_cents: 12499,
      last_observed_at: STALE_LISTING_OBSERVED_AT,
      observation_count: 2,
    },
  ],
  history: MOCK_PRICE_HISTORY_ARRAY,
  window: '90d',
};

const MOCK_LISTINGS_MULTI = [
  {
    id: 'listing-fresh',
    part_id: MULTI_PART_ID,
    retailer_id: 'r1',
    product_url: 'https://retailer-one.example.com/product/multi-001',
    last_known_price_cents: 11999,
    last_price_updated_at: FRESH_LISTING_OBSERVED_AT,
    created_at: FIXED_NOW_ISO,
    updated_at: FIXED_NOW_ISO,
    retailer: {
      id: 'r1',
      name: 'RetailerOne',
      domain: 'retailer-one.example.com',
      base_url: 'https://retailer-one.example.com',
      is_active: true,
      created_at: FIXED_NOW_ISO,
      updated_at: FIXED_NOW_ISO,
    },
  },
  {
    id: 'listing-stale',
    part_id: MULTI_PART_ID,
    retailer_id: 'r2',
    product_url: 'https://retailer-two.example.com/product/multi-001',
    last_known_price_cents: 12499,
    last_price_updated_at: STALE_LISTING_OBSERVED_AT,
    created_at: FIXED_NOW_ISO,
    updated_at: FIXED_NOW_ISO,
    retailer: {
      id: 'r2',
      name: 'RetailerTwo',
      domain: 'retailer-two.example.com',
      base_url: 'https://retailer-two.example.com',
      is_active: true,
      created_at: FIXED_NOW_ISO,
      updated_at: FIXED_NOW_ISO,
    },
  },
];

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
 * Serve the catalog and part detail API contract from fixtures as an anonymous
 * viewer, counting batch price-history POSTs in `counters` and 404ing the rest.
 *
 * The route matcher excludes Vite source modules at `/src/api/*.ts`, which
 * would otherwise be served as JSON and crash the bundle load.
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
        return jsonResponse(route, { detail: 'Not authenticated' }, 401);
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
        const isLegacy = url.searchParams.get('legacy') === 'true';
        if (isLegacy) {
          return jsonResponse(
            route,
            partId === MULTI_PART_ID ? MOCK_PRICE_HISTORY_ARRAY : []
          );
        }
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

      const listingsMatch = path.match(/^\/parts\/([^/]+)\/listings$/);
      if (listingsMatch && method === 'GET') {
        const partId = listingsMatch[1];
        if (partId === MULTI_PART_ID) {
          return jsonResponse(route, MOCK_LISTINGS_MULTI);
        }
        return jsonResponse(route, []);
      }

      const partMatch = path.match(/^\/parts\/([^/]+)$/);
      if (partMatch && method === 'GET') {
        const partId = partMatch[1];
        const part = MOCK_PARTS[partId];
        if (!part) {
          return jsonResponse(route, { detail: 'Not found' }, 404);
        }
        return jsonResponse(route, part);
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

      const userMatch = path.match(/^\/users\/([^/]+)$/);
      if (userMatch && method === 'GET') {
        return jsonResponse(route, MOCK_SERVICE_USER);
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
 * Install the API mocks and pin the clock so the 60 day stale-caveat threshold
 * resolves the same way on every run.
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

test('/parts catalog renders sparklines + delta lines', async ({ page }) => {
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
  await expect(page.getByText('$120 → $150').first()).toBeVisible();

  const zeroRow = page.getByRole('link', {
    name: MOCK_PARTS[ZERO_PART_ID].name,
  });
  await expect(zeroRow.first()).toBeVisible();
  await expect(page.locator(`[data-part-id="${ZERO_PART_ID}"]`)).toHaveCount(0);

  expect(counters.batchPriceHistoryPostCount).toBe(1);
  expect(observedBatchPosts).toBe(1);

  await expect(page).toHaveScreenshot({ fullPage: true });
});

test('/parts/:id detail renders retailer breakdown + stale caveat', async ({
  page,
}) => {
  await setupPage(page);

  await page.goto(`/parts/${MULTI_PART_ID}`);
  await waitForPageReady(page);

  await expect(
    page.getByRole('heading', { name: 'Price by retailer' })
  ).toBeVisible();

  const staleCaveat = `(as of ${STALE_LISTING_LOCAL_DATE})`;
  await expect(page.getByText(staleCaveat).first()).toBeVisible();

  await expect(page.getByText(staleCaveat)).toHaveCount(1);

  await expect(page).toHaveScreenshot({ fullPage: true });
});

test('/parts/:id with zero observations hides Price summary block', async ({
  page,
}) => {
  await setupPage(page);

  await page.goto(`/parts/${ZERO_PART_ID}`);
  await waitForPageReady(page);

  await expect(page.locator('[data-testid="retailer-row"]')).toHaveCount(0);
  await expect(
    page.locator('[data-testid="price-summary-header"]')
  ).toHaveCount(0);
  await expect(
    page.getByText('No retailer pricing observed yet.')
  ).toBeVisible();
});
