/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get) is the canonical Phase 8 mocking pattern.
 */

// Phase 8 plan 08-14 (D-11) — ViewUser public-profile render + 404 path.
//
// ViewUser imports `apiClient` from `../api/client` and `buildListsApi` from
// `../api/build_lists`. setup.ts mocks the client, and the domain module calls
// through it, so both paths land on the same mocked Axios surface.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import ViewUser from './ViewUser';

describe('ViewUser page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders a public user profile when the user fetch succeeds', async () => {
    // First call is GET /users/:id → returns the profile; second call is
    // GET /build-lists/user/:id → returns an empty list.
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/users/')) {
        return Promise.resolve({ data: mockUser });
      }
      if (url.startsWith('/build-lists/user/')) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/user/${mockUser.id}`]}>
        <Routes>
          <Route path="/user/:userId" element={<ViewUser />} />
        </Routes>
      </MemoryRouter>
    );

    // PageHeader renders `Profile: <username>` plus a Username CardInfoItem.
    await waitFor(() =>
      expect(
        screen.getByRole('heading', {
          name: new RegExp(`profile: ${mockUser.username}`, 'i'),
        })
      ).toBeInTheDocument()
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/users/${mockUser.id}`
    );
    expect(
      screen.getByText(/this user has no public build lists yet/i)
    ).toBeInTheDocument();
  });

  it('shows an error card when the user fetch returns 404', async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { status: 404 } });

    render(
      <MemoryRouter initialEntries={['/user/missing-user-id']}>
        <Routes>
          <Route path="/user/:userId" element={<ViewUser />} />
        </Routes>
      </MemoryRouter>
    );

    // Source renders `ErrorAlert` with "Failed to load profile for User ID
    // "<id>". <error-message>" when userApiError is set.
    await waitFor(() =>
      expect(
        screen.getByText(
          /failed to load profile for user id "missing-user-id"/i
        )
      ).toBeInTheDocument()
    );
  });
});
