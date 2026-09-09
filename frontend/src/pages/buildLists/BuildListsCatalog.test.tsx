// Phase 8 plan 08-13 (D-11) — page test for BuildListsCatalog.
//
// The page calls:
//   - carGenerationsApi.getCarMakeStats()        → GET /car-generations/stats/car-makes
//   - buildListsApi.getBuildListsWithVotes(...)  → GET /build-lists/with-votes
//   - carGenerationsApi.getCar(carId) (URL init) → GET /car-generations/:id
//   - carGenerationsApi.getCarsByMake(make)      → GET /car-generations/car-makes/:make
//
// Tests exercise: (1) render with data, (2) empty state, (3) car_id URL
// deeplink forwards to API.
//
// buildListsApi and carGenerationsApi come from their `../../api/<domain>`
// modules, which call through the apiClient that setup.ts mocks, so no
// per-file module mock is needed.

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { apiClient } from '../../api/client';
import { mockBuildList, mockCar } from '../../test/mocks/api';
import BuildListsCatalog from './BuildListsCatalog';

// Helper: seed the apiClient.get mock with a URL-routed implementation so
// initial mount (make stats + paginated build-lists fetch) resolves with the
// requested shape.
function seedApiClient(buildLists: (typeof mockBuildList)[] = [mockBuildList]) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes('/car-generations/stats/car-makes')) {
      return Promise.resolve({ data: { Toyota: 1 } });
    }
    if (url.includes('/car-generations/car-makes/')) {
      return Promise.resolve({ data: [mockCar] });
    }
    if (url.includes('/car-generations/') && !url.includes('stats')) {
      // GET /car-generations/:id — used for ?car_id=... deeplink
      return Promise.resolve({ data: mockCar });
    }
    if (url.includes('/build-lists/with-votes')) {
      return Promise.resolve({
        data: {
          data: buildLists.map((bl) => ({
            ...bl,
            upvotes: 0,
            downvotes: 0,
            total_votes: 0,
            user_vote: null,
            total_cost_cents: 0,
          })),
          pagination: {
            current_page: 1,
            total_pages: 1,
            total_items: buildLists.length,
            items_per_page: 12,
            has_next: false,
            has_previous: false,
          },
        },
      });
    }
    return Promise.resolve({ data: null });
  });
}

describe('BuildListsCatalog page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedApiClient();
  });

  it('renders build list catalog with results', async () => {
    render(
      <MemoryRouter initialEntries={['/build-lists']}>
        <BuildListsCatalog />
      </MemoryRouter>
    );

    // Static page header + section title render synchronously.
    expect(screen.getByText('Build Lists Catalog')).toBeInTheDocument();
    expect(screen.getByText('All Build Lists')).toBeInTheDocument();

    // Build list card name resolves from paginated fetch.
    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

    // Paginated endpoint was hit at least once.
    expect(
      vi
        .mocked(apiClient.get)
        .mock.calls.some(([url]) =>
          String(url).includes('/build-lists/with-votes')
        )
    ).toBe(true);
  });

  it('shows empty state when no build lists are returned', async () => {
    seedApiClient([]);

    render(
      <MemoryRouter initialEntries={['/build-lists']}>
        <BuildListsCatalog />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(/no build lists found/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(mockBuildList.name)).not.toBeInTheDocument();
  });

  it('forwards car_id deeplink filter to the car-generations API', async () => {
    render(
      <MemoryRouter initialEntries={[`/build-lists?car_id=${mockCar.id}`]}>
        <BuildListsCatalog />
      </MemoryRouter>
    );

    // Wait for initial effect chain: page first fetches make stats, then
    // carFromUrl, then cars-by-make. The deeplink car_id should flow into a
    // GET /car-generations/:id call.
    await waitFor(() => {
      const calls = vi.mocked(apiClient.get).mock.calls;
      const deeplinked = calls.some(([url]) => {
        const u = String(url);
        return u.includes('/car-generations/') && u.includes(mockCar.id);
      });
      expect(deeplinked).toBe(true);
    });
  });
});
