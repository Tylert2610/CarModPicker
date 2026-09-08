/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get) is the canonical Wave 1 mocking pattern. The
 * unbound-method rule flags the reference syntactically; vi.mocked returns
 * a spy so `this` binding is not a real concern here.
 */
import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../api/client';
import { mockCar, mockCategory } from '../test/mocks/api';
import { usePartsFilters } from './usePartsFilters';

// Phase 8 D-09 — usePartsFilters is the URL-state-backed filter hook used
// by /parts. It pulls categories, makes, manufacturers, and the filter-options
// response from the API (all mocked via setup.ts) and exposes the derived
// params + setters that the parts page feeds to partsApi.getParts.
//
// We focus on the highest-branch-density surfaces: initial state shape,
// URL-derived initialization, setter branches, and clearAllFilters reset.
//
// The hook imports `partsApi`, `categoriesApi`, `carGenerationsApi`, and
// `partManufacturersApi` from their `../api/<domain>` modules. Those modules
// call the shared apiClient, which setup.ts already mocks, so no per-file
// module mock is needed.

function routerWrapper(initialEntries: string[]) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
  );
  return Wrapper;
}

beforeEach(() => {
  vi.clearAllMocks();

  // Default responses for the cascade of fetches the hook kicks off on mount.
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/categories/') {
      return Promise.resolve({ data: [mockCategory] });
    }
    if (url === '/part-manufacturers/') {
      return Promise.resolve({ data: [] });
    }
    if (url.startsWith('/car-generations/stats/car-makes')) {
      return Promise.resolve({ data: { Toyota: 1 } });
    }
    if (url.startsWith('/car-generations/') && !url.includes('filter')) {
      return Promise.resolve({ data: mockCar });
    }
    if (url.startsWith('/car-generations')) {
      return Promise.resolve({ data: [mockCar] });
    }
    if (url === '/parts/filter-options') {
      return Promise.resolve({
        data: {
          category_ids: [mockCategory.id],
          part_manufacturer_ids: [],
          car_ids: [mockCar.id],
          make_names: ['Toyota'],
        },
      });
    }
    return Promise.resolve({ data: null });
  });
});

describe('usePartsFilters — initial state', () => {
  it('returns empty filters and default sort when no URL params and syncToUrl=false', async () => {
    const { result } = renderHook(() => usePartsFilters(), {
      wrapper: routerWrapper(['/parts']),
    });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalled();
    });

    expect(result.current.selectedCategoryIds).toEqual([]);
    expect(result.current.selectedMake).toBe('');
    expect(result.current.showUniversalParts).toBe(false);
    expect(result.current.sortParam).toBe('votes_desc');
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('exposes pagination defaults and derived params', () => {
    const { result } = renderHook(() => usePartsFilters(), {
      wrapper: routerWrapper(['/parts']),
    });

    expect(result.current.currentPage).toBe(1);
    expect(result.current.params.skip).toBe(0);
    expect(result.current.params.limit).toBe(100);
    expect(result.current.params.sort).toBe('votes_desc');
  });
});

describe('usePartsFilters — setters', () => {
  it('toggleCategory adds then removes a category id', () => {
    const { result } = renderHook(() => usePartsFilters(), {
      wrapper: routerWrapper(['/parts']),
    });

    act(() => {
      result.current.toggleCategory('cat-1');
    });
    expect(result.current.selectedCategoryIds).toEqual(['cat-1']);

    act(() => {
      result.current.toggleCategory('cat-1');
    });
    expect(result.current.selectedCategoryIds).toEqual([]);
  });

  it('setSearchTerm + setPriceMin produce derived price_cents + search params', () => {
    const { result } = renderHook(() => usePartsFilters(), {
      wrapper: routerWrapper(['/parts']),
    });

    act(() => {
      result.current.setSearchTerm('intake');
      result.current.setPriceMin('25.50');
      result.current.setPriceMax('100');
    });

    expect(result.current.params.search).toBe('intake');
    expect(result.current.params.min_price_cents).toBe(2550);
    expect(result.current.params.max_price_cents).toBe(10000);
    expect(result.current.hasPriceRange).toBe(true);
  });

  it('setShowUniversalParts flips the universal param', () => {
    const { result } = renderHook(() => usePartsFilters(), {
      wrapper: routerWrapper(['/parts']),
    });

    act(() => {
      result.current.setShowUniversalParts(true);
    });

    expect(result.current.showUniversalParts).toBe(true);
    expect(result.current.params.universal).toBe(true);
  });

  it('clearAllFilters resets every user-driven filter', () => {
    const { result } = renderHook(() => usePartsFilters(), {
      wrapper: routerWrapper(['/parts']),
    });

    act(() => {
      result.current.setSearchTerm('brakes');
      result.current.setPriceMin('10');
      result.current.setShowUniversalParts(true);
      result.current.toggleCategory('cat-1');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    act(() => {
      result.current.clearAllFilters();
    });

    expect(result.current.selectedCategoryIds).toEqual([]);
    expect(result.current.searchTerm).toBe('');
    expect(result.current.priceMin).toBe('');
    expect(result.current.showUniversalParts).toBe(false);
    expect(result.current.hasActiveFilters).toBe(false);
  });
});

describe('usePartsFilters — user-scoped variant', () => {
  it('forwards user_id into params when the option is set', () => {
    const userId = '11111111-1111-7111-8111-111111111111';
    const { result } = renderHook(() => usePartsFilters({ user_id: userId }), {
      wrapper: routerWrapper(['/parts']),
    });

    expect(result.current.params.user_id).toBe(userId);
  });
});
