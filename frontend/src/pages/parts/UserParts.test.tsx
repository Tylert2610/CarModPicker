// Phase 8 Wave 3 page test — UserParts renders the authenticated user's
// parts list and exposes an auth-gated error state when unauthenticated.
//
// This file builds a local render that wraps children in <MemoryRouter> and
// seeds useAuth via the same mockUseAuth singleton test-utils uses, so the
// auth scenario is set per test without going through customRender.
/* eslint-disable @typescript-eslint/unbound-method */
import type { ReactElement, ReactNode } from 'react';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { mockCategory, mockPart, mockUser } from '../../test/mocks/api';
import type { UserRead } from '../../types/Api';
import UserParts from './UserParts';

// Mock useAuth the same way TestProviders does, swapping the auth state per
// scenario.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// usePartsFilters, PartList and UserParts reach the API through their
// `../../api/<domain>` modules, which call the apiClient that setup.ts mocks.
// Import apiClient AFTER the vi.mock declarations so it resolves to that mock.
import { apiClient } from '../../api/client';

// PartList depends on ResizeObserver (via useContainerWidth). Stub globally
// so mounting in jsdom does not throw when the callback ref attaches.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

interface AuthState {
  isAuthenticated: boolean;
  user: UserRead | null;
  isLoading?: boolean;
}

const seedAuth = (state: AuthState) => {
  mockUseAuth.mockReturnValue({
    isAuthenticated: state.isAuthenticated,
    user: state.user,
    isLoading: state.isLoading ?? false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  });
};

const renderWithRouter = (
  ui: ReactElement,
  { route = '/my-parts' }: { route?: string } = {}
) =>
  rtlRender(ui, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
    ),
  });

const makePaginatedPartsResponse = (
  items: (typeof mockPart)[] = [mockPart]
) => ({
  data: items.map((p) => ({
    ...p,
    upvotes: 0,
    downvotes: 0,
    total_votes: 0,
    user_vote: null,
  })),
  pagination: {
    current_page: 1,
    total_pages: 1,
    total_items: items.length,
    items_per_page: 100,
    has_next: false,
    has_previous: false,
  },
});

describe('UserParts page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists the authenticated user's parts from the API", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/parts/with-votes')) {
        return Promise.resolve({ data: makePaginatedPartsResponse() });
      }
      if (url.startsWith('/parts/filter-options')) {
        return Promise.resolve({
          data: {
            category_ids: [mockCategory.id],
            part_manufacturer_ids: [],
            car_ids: [],
            make_names: [],
          },
        });
      }
      if (url.startsWith('/categories')) {
        return Promise.resolve({ data: [mockCategory] });
      }
      return Promise.resolve({ data: [] });
    });

    seedAuth({ isAuthenticated: true, user: mockUser });
    renderWithRouter(<UserParts />);

    expect(screen.getByText(/my parts/i)).toBeInTheDocument();

    // usePartsFilters scopes the list to the authenticated user_id. Verify
    // a /parts/with-votes call was made.
    await waitFor(() => {
      const calls = vi.mocked(apiClient.get).mock.calls.map(([url]) => url);
      expect(calls.some((u) => u.startsWith('/parts/with-votes'))).toBe(true);
    });

    await waitFor(() => {
      expect(screen.getByText(mockPart.name)).toBeInTheDocument();
    });
  });

  it('renders the empty-state copy when the user has no parts', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/parts/with-votes')) {
        return Promise.resolve({ data: makePaginatedPartsResponse([]) });
      }
      if (url.startsWith('/parts/filter-options')) {
        return Promise.resolve({
          data: {
            category_ids: [],
            part_manufacturer_ids: [],
            car_ids: [],
            make_names: [],
          },
        });
      }
      if (url.startsWith('/categories')) {
        return Promise.resolve({ data: [mockCategory] });
      }
      return Promise.resolve({ data: [] });
    });

    seedAuth({ isAuthenticated: true, user: mockUser });
    renderWithRouter(<UserParts />);

    // Empty-state copy is wired in UserParts.tsx:168 —
    // "You haven't created any parts yet. ..."
    await waitFor(() => {
      expect(
        screen.getByText(/haven't created any parts yet/i)
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(mockPart.name)).not.toBeInTheDocument();
  });

  it('shows a login-required error when the viewer is unauthenticated', () => {
    // Unauthenticated short-circuits in UserParts.tsx:129 before any fetch
    // runs.
    seedAuth({ isAuthenticated: false, user: null });
    renderWithRouter(<UserParts />);

    expect(
      screen.getByText(/must be logged in to view your parts/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(mockPart.name)).not.toBeInTheDocument();
  });
});
