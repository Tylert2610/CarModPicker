import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom ResizeObserver stub — kept defensively for downstream charts.
class ResizeObserverStub {
  constructor(_cb: ResizeObserverCallback) {
    void _cb;
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

import { apiClient } from '../../api/client';
import {
  mockCategory,
  mockPart,
  mockUser,
  mockVoteSummary,
} from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import type {
  PartListingReadWithRetailer,
  PriceHistorySinglePartResponse,
  RetailerPriceBreakdown,
} from '../../types/Api';
import ViewPart from './ViewPart';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

function seedAuthenticated(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    user: mockUser,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

const RECENTLY_OBSERVED_AT = new Date(
  Date.now() - 24 * 60 * 60 * 1000
).toISOString();

function makeRetailer(
  overrides: Partial<RetailerPriceBreakdown> & { retailer_id: string }
): RetailerPriceBreakdown {
  const base: RetailerPriceBreakdown = {
    retailer_id: overrides.retailer_id,
    retailer_name: `Retailer ${overrides.retailer_id}`,
    min_cents: 1000,
    max_cents: 2000,
    last_cents: 1500,
    last_observed_at: RECENTLY_OBSERVED_AT,
    observation_count: 3,
  };
  return { ...base, ...overrides };
}

function makeListing(
  id: string,
  retailerName: string,
  daysAgo: number | null,
  overrides: Partial<PartListingReadWithRetailer> = {}
): PartListingReadWithRetailer {
  const updated =
    daysAgo === null
      ? null
      : new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000).toISOString();
  return {
    id,
    part_id: mockPart.id,
    retailer_id: `r-${id}`,
    product_url: `https://example.com/${id}`,
    last_known_price_cents: 1500,
    last_price_updated_at: updated,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: updated ?? '2026-01-01T00:00:00Z',
    retailer: {
      id: `r-${id}`,
      name: retailerName,
      domain: null,
      base_url: null,
      is_active: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    ...overrides,
  };
}

interface InstallOpts {
  summary: PriceHistorySinglePartResponse;
  listings?: PartListingReadWithRetailer[];
}

function installGetRouting({ summary, listings = [] }: InstallOpts): void {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === `/parts/${mockPart.id}`) {
      return Promise.resolve({ data: mockPart });
    }
    if (url === `/votes/part/${mockPart.id}/summary`) {
      return Promise.resolve({ data: mockVoteSummary });
    }
    if (url === '/categories/') {
      return Promise.resolve({ data: [mockCategory] });
    }
    if (url === `/users/${mockUser.id}`) {
      return Promise.resolve({ data: mockUser });
    }
    if (url === `/parts/${mockPart.id}/listings`) {
      return Promise.resolve({ data: listings });
    }
    if (url === `/parts/${mockPart.id}/price-history`) {
      return Promise.resolve({ data: summary });
    }
    return Promise.resolve({ data: null });
  });
}

function renderViewPart() {
  return render(
    <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
      <Routes>
        <Route path="/parts/:partId" element={<ViewPart />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ViewPart Price by retailer block (collapsed)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('does not render the Price by retailer block when observation_count is 0 AND listings empty', async () => {
    const summary: PriceHistorySinglePartResponse = {
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
    };
    installGetRouting({ summary });

    renderViewPart();

    // Page loads.
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: mockPart.name })
      ).toBeInTheDocument()
    );

    // Section header is always rendered (sibling of subscribe button), but
    // the body — the table + summary header — should not appear.
    expect(
      screen.queryByTestId('price-summary-header')
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('retailer-row')).not.toBeInTheDocument();
    // Empty-state copy renders instead.
    expect(
      screen.getByText('No retailer pricing observed yet.')
    ).toBeInTheDocument();
  });

  it('renders one retailer-row per priceSummary.retailers entry — no tabs', async () => {
    const retailers = [
      makeRetailer({ retailer_id: 'r1', retailer_name: 'Acme Parts' }),
      makeRetailer({ retailer_id: 'r2', retailer_name: 'Bravo Auto' }),
      makeRetailer({ retailer_id: 'r3', retailer_name: 'Charlie Speed' }),
      makeRetailer({ retailer_id: 'r4', retailer_name: 'Delta Performance' }),
      makeRetailer({ retailer_id: 'r5', retailer_name: 'Echo Tuning' }),
    ];
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 900,
        max_cents: 2100,
        last_cents: 1500,
        last_observed_at: RECENTLY_OBSERVED_AT,
        trend: 'down',
        observation_count: 6,
      },
      retailers,
      history: [],
      window: '90d',
    };
    installGetRouting({ summary });

    renderViewPart();

    await waitFor(() =>
      expect(screen.getByTestId('price-summary-header')).toBeInTheDocument()
    );

    // One row per retailer, no tabs anywhere.
    expect(screen.getAllByTestId('retailer-row')).toHaveLength(
      retailers.length
    );
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    for (const r of retailers) {
      expect(screen.getByText(r.retailer_name)).toBeInTheDocument();
    }
  });

  it('renders the one-line summary header above the table when observation_count > 0', async () => {
    const retailers = [
      makeRetailer({
        retailer_id: 'r1',
        retailer_name: 'Acme Parts',
        last_cents: 1200,
      }),
      makeRetailer({
        retailer_id: 'r2',
        retailer_name: 'Bravo Auto',
        last_cents: 1800,
      }),
    ];
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 900,
        max_cents: 2100,
        last_cents: 1500,
        last_observed_at: RECENTLY_OBSERVED_AT,
        trend: 'down',
        observation_count: 6,
      },
      retailers,
      history: [],
      window: '90d',
    };
    installGetRouting({ summary });

    renderViewPart();

    const header = await waitFor(() =>
      screen.getByTestId('price-summary-header')
    );
    // Format: $9.00–$21.00 across 2 retailers, last observed ↓ <date>
    expect(header.textContent).toContain('$9.00');
    expect(header.textContent).toContain('$21.00');
    expect(header.textContent).toContain('across 2 retailers');
    expect(header.textContent).toContain('last observed');
    expect(header.textContent).toContain('↓');
  });

  it('shows the stale caveat exactly once for a retailer with last_observed_at 90 days ago', async () => {
    const ninetyDaysAgo = new Date(
      Date.now() - 90 * 24 * 60 * 60 * 1000
    ).toISOString();
    const retailers = [
      makeRetailer({
        retailer_id: 'r1',
        retailer_name: 'Fresh Shop',
        last_observed_at: RECENTLY_OBSERVED_AT,
      }),
      makeRetailer({
        retailer_id: 'r2',
        retailer_name: 'Stale Shop',
        last_observed_at: ninetyDaysAgo,
      }),
    ];
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 1000,
        max_cents: 2000,
        last_cents: 1500,
        last_observed_at: RECENTLY_OBSERVED_AT,
        trend: 'flat',
        observation_count: 5,
      },
      retailers,
      history: [],
      window: '90d',
    };
    installGetRouting({ summary });

    renderViewPart();

    await waitFor(() =>
      expect(screen.getByText('Stale Shop')).toBeInTheDocument()
    );

    // Single source of truth for the stale caveat — exactly one occurrence.
    const staleMatches = screen.getAllByText(/as of/i);
    expect(staleMatches).toHaveLength(1);
  });

  it("renders View at retailer link with target=_blank rel='noopener noreferrer' + ExternalLink svg", async () => {
    const retailers = [
      makeRetailer({ retailer_id: 'r-L1', retailer_name: 'Linked Shop' }),
    ];
    const summary: PriceHistorySinglePartResponse = {
      summary: {
        min_cents: 1500,
        max_cents: 1500,
        last_cents: 1500,
        last_observed_at: RECENTLY_OBSERVED_AT,
        trend: 'flat',
        observation_count: 3,
      },
      retailers,
      history: [],
      window: '90d',
    };
    // makeListing assigns retailer_id = `r-${id}` — pass id "L1" to align
    // with the retailer above so the join produces a product_url.
    const listings = [makeListing('L1', 'Linked Shop', 5)];
    installGetRouting({ summary, listings });

    renderViewPart();

    const link = await waitFor(() =>
      screen.getByRole('link', { name: /View at retailer/i })
    );
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    // Lucide ExternalLink renders as an <svg> child of the link.
    expect(link.querySelector('svg')).not.toBeNull();
  });
});
