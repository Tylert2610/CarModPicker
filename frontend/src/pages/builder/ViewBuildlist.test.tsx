// Phase 8 plan 08-11 (D-11) — page test for ViewBuildlist (the deepest
// /build-lists/:buildListId page: 463 lines, 5 fetches on mount + a parts
// subsection).
//
// Fetches exercised:
//   - /build-lists/{id}                 (build list)
//   - /car-generations/{carId}          (associated car — fires after build list)
//   - /users/{userId}                   (owner)
//   - /votes/build_list/{id}/summary    (vote summary via buildListVotesApi)
//   - /build-list-parts/{id}/parts      (nested BuildListParts component)
//   - /build-lists/{id}/phases          (phases fetch from BuildListParts)
//
// testScenarios.authenticated is the canonical auth fixture (Phase 8 D-05);
// we inline its shape locally so this file sets the auth branch without going
// through customRender.

/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get) is the canonical Vitest pattern for typed mock
 * introspection; same rationale as AuthContext.test.tsx.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom does not implement ResizeObserver, but ViewBuildList → BuildListParts →
// ResponsiveTableWrapper → useContainerWidth constructs one. Stub it so the
// commitAttachRef layout-effect doesn't throw. Matches App.coverage.test.tsx.
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
  mockBuildList,
  mockCar,
  mockPart,
  mockUser,
  mockVoteSummary,
} from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import ViewBuildList from './ViewBuildlist';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Inlined equivalent of testScenarios.authenticated (D-05).
const authenticatedAuthState = {
  isAuthenticated: true,
  isLoading: false,
} as const;

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

type BuildListPartRow = {
  id: string;
  build_list_id: string;
  part_id: string;
  quantity: number;
  build_list_phase_id: string | null;
  is_purchased: boolean;
  is_installed: boolean;
  created_at: string;
  updated_at: string;
  part: typeof mockPart;
};

function makeBuildListPart(): BuildListPartRow {
  return {
    id: '66666666-6666-7666-8666-666666666666',
    build_list_id: mockBuildList.id,
    part_id: mockPart.id,
    quantity: 1,
    build_list_phase_id: null,
    is_purchased: false,
    is_installed: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    part: mockPart,
  };
}

describe('ViewBuildList page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the build list name, owner, and associated car when fetches succeed', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/build-lists/${mockBuildList.id}`) {
        return Promise.resolve({ data: mockBuildList });
      }
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.resolve({ data: mockCar });
      }
      if (url === `/users/${mockUser.id}`) {
        return Promise.resolve({ data: mockUser });
      }
      if (url === `/votes/build_list/${mockBuildList.id}/summary`) {
        return Promise.resolve({
          data: { ...mockVoteSummary, entity_type: 'build_list' },
        });
      }
      if (url === `/build-list-parts/${mockBuildList.id}/parts`) {
        return Promise.resolve({ data: [makeBuildListPart()] });
      }
      if (url === `/build-lists/${mockBuildList.id}/phases`) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/build-lists/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-lists/:buildListId" element={<ViewBuildList />} />
        </Routes>
      </MemoryRouter>
    );

    // Page-level header swaps from "Build List Details" loader to the name.
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: mockBuildList.name })
      ).toBeInTheDocument()
    );

    // Build list info card sections render after fetch.
    expect(screen.getByText('Build List Information')).toBeInTheDocument();
    expect(screen.getByText('Description:')).toBeInTheDocument();

    // Associated car card label resolves once /car-generations/{id} returns.
    await waitFor(() =>
      expect(screen.getByText('Associated Car:')).toBeInTheDocument()
    );

    // Owner section resolves once /users/{id} returns.
    await waitFor(() =>
      expect(screen.getByText('Build List Owner:')).toBeInTheDocument()
    );

    // Confirm the canonical fetches happened.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}`
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/car-generations/${mockCar.id}`
    );
  });

  it('renders the parts section with at least one part row when BuildListParts resolves', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/build-lists/${mockBuildList.id}`) {
        return Promise.resolve({ data: mockBuildList });
      }
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.resolve({ data: mockCar });
      }
      if (url === `/users/${mockUser.id}`) {
        return Promise.resolve({ data: mockUser });
      }
      if (url === `/votes/build_list/${mockBuildList.id}/summary`) {
        return Promise.resolve({
          data: { ...mockVoteSummary, entity_type: 'build_list' },
        });
      }
      if (url === `/build-list-parts/${mockBuildList.id}/parts`) {
        return Promise.resolve({ data: [makeBuildListPart()] });
      }
      if (url === `/build-lists/${mockBuildList.id}/phases`) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/build-lists/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-lists/:buildListId" element={<ViewBuildList />} />
        </Routes>
      </MemoryRouter>
    );

    // "Parts in <name>" section heading (rendered inside BuildListParts).
    await waitFor(() =>
      expect(
        screen.getByText(new RegExp(`Parts in ${mockBuildList.name}`, 'i'))
      ).toBeInTheDocument()
    );

    // The part row surfaces the part name from mockPart.
    await waitFor(() =>
      expect(screen.getAllByText(mockPart.name).length).toBeGreaterThan(0)
    );
  });

  it('renders the empty-parts message when BuildListParts resolves empty', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/build-lists/${mockBuildList.id}`) {
        return Promise.resolve({ data: mockBuildList });
      }
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.resolve({ data: mockCar });
      }
      if (url === `/users/${mockUser.id}`) {
        return Promise.resolve({ data: mockUser });
      }
      if (url === `/votes/build_list/${mockBuildList.id}/summary`) {
        return Promise.resolve({
          data: { ...mockVoteSummary, entity_type: 'build_list' },
        });
      }
      if (url === `/build-list-parts/${mockBuildList.id}/parts`) {
        return Promise.resolve({ data: [] });
      }
      if (url === `/build-lists/${mockBuildList.id}/phases`) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/build-lists/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-lists/:buildListId" element={<ViewBuildList />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(/currently has no parts/i)).toBeInTheDocument()
    );
  });
});
