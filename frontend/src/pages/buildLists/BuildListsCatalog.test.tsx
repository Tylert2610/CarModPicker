import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { apiClient } from '../../api/client';
import { mockBuildList, mockCar } from '../../test/mocks/api';
import BuildListsCatalog from './BuildListsCatalog';

function seedApiClient(buildLists: (typeof mockBuildList)[] = [mockBuildList]) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes('/car-generations/stats/car-makes')) {
      return Promise.resolve({ data: { Toyota: 1 } });
    }
    if (url.includes('/car-generations/car-makes/')) {
      return Promise.resolve({ data: [mockCar] });
    }
    if (url.includes('/car-generations/') && !url.includes('stats')) {
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

    expect(screen.getByText('Build Lists Catalog')).toBeInTheDocument();
    expect(screen.getByText('All Build Lists')).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

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
