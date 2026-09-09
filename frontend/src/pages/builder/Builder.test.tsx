// Phase 8 plan 08-11 (D-11) — page test for Builder.
//
// Builder is a /builder-scoped dashboard that loads the current user's build
// lists via buildListsApi.getBuildListsWithVotes() (paginated). We exercise
// the authenticated happy path (build-list cards render) + the empty-state
// fallback ("no build lists yet…").
//
// Per PATTERNS.md §11 we use testScenarios.authenticated for the auth fixture.
// We use raw `render` from @testing-library/react + a MemoryRouter + direct
// mockUseAuth setup (rather than customRender) so we can preload per-test
// apiClient mocks BEFORE mount — the customRender in test-utils.tsx calls
// setupApiMocks() which would clobber per-test mock impls otherwise.

/* eslint-disable @typescript-eslint/no-unsafe-assignment --
 * vi.mocked(apiClient.get) is the canonical Vitest pattern for typed mock
 * introspection (mirrors AuthContext.test.tsx). The unsafe-assignment warning
 * fires on the nested `data: { data: [...], pagination: {...} }` literal used
 * as a mock return — Vitest's MockResolvedValue type is loose enough that
 * strict mode calls the payload `any`. Safe here because we hand-roll the
 * payload against the real PaginatedResponse<BuildListReadWithVotes> shape.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import { mockBuildList, mockUser } from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import Builder from './Builder';

// Auth fixture. Mirrors the canonical `testScenarios.authenticated` shape from
// `src/test/utils/test-utils.tsx` (Phase 8 D-05) without importing that module
// — importing test-utils would also pull in its own vi.mock('../../services/
// Api') which clobbers our importActual-based extension below. We inline the
// same logical fixture (isAuthenticated: true, isLoading: false) here.
const authenticatedAuthState = {
  isAuthenticated: true,
  isLoading: false,
} as const;
// Hint to readers: this is equivalent to testScenarios.authenticated.

function seedAuthenticated(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: authenticatedAuthState.isAuthenticated,
    user: mockUser,
    isLoading: authenticatedAuthState.isLoading,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

// Needed because test-utils.tsx registers vi.mock('../../hooks/useAuth')
// only when its file is imported. This page test does NOT import test-utils,
// so we register the mock here against the same hook.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Builder imports `buildListsApi` from `../../api/build_lists`, which calls
// the apiClient that setup.ts mocks, so no per-file module mock is needed.

describe('Builder page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the build list grid when the user has build lists', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        data: [{ ...mockBuildList, total_votes: 3, total_cost_cents: 25000 }],
        pagination: {
          current_page: 1,
          total_pages: 1,
          total_items: 1,
          items_per_page: 8,
          has_next: false,
          has_previous: false,
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/builder']}>
        <Builder />
      </MemoryRouter>
    );

    // Page header is present immediately.
    expect(screen.getByText('Builder')).toBeInTheDocument();

    // Build list card renders after fetch resolves.
    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

    // Create-new tile is shown on the first page.
    expect(screen.getByText(/Create New Build List/i)).toBeInTheDocument();

    // Confirm the request targeted the enriched (with-votes) endpoint.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/build-lists/with-votes',
      expect.objectContaining({
        params: expect.objectContaining({ owner_id: mockUser.id }),
      })
    );
  });

  it('renders the empty state when the user has no build lists', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        data: [],
        pagination: {
          current_page: 1,
          total_pages: 0,
          total_items: 0,
          items_per_page: 8,
          has_next: false,
          has_previous: false,
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/builder']}>
        <Builder />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/don't have any build lists yet/i)
      ).toBeInTheDocument()
    );

    // The create-new tile is still visible on page 1 in the empty state.
    expect(screen.getByText(/Create New Build List/i)).toBeInTheDocument();
  });
});
