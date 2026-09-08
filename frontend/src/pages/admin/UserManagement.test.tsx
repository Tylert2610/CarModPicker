/* eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/no-unsafe-assignment --
 * vi.mocked(apiClient.*) is the canonical Phase 8 mocking pattern.
 * `expect.objectContaining(...)` returns `any` and trips no-unsafe-assignment
 * when nested as a property value — false positive in this matcher pattern.
 */

// Phase 8 plan 08-16 (Wave 4) — UserManagement admin page coverage.
//
// UserManagement imports `usersApi` from `../../api/users` and uses that
// module's `getAllUsers`, `adminUpdateUser`, `adminDeleteUser` methods, which
// call the apiClient that setup.ts mocks.
//
// Manual BrowserRouter + mockUseAuth wire-up per the pattern established in
// Profile.test.tsx / BugReport.test.tsx, so this file controls the auth
// branch directly.

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { testScenarios } from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { makeAdminUserView, makeUserList } from '../../test/mocks/admin/users';
import type { PaginatedResponse, UserRead } from '../../types/Api';

// Use the canonical admin scenario fixture for the authenticated-admin user.
const adminUser = testScenarios.adminAuthenticated.initialAuthState.user;

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import UserManagement from './UserManagement';

const makePaginatedUserList = (
  items: UserRead[] = makeUserList()
): PaginatedResponse<UserRead> => ({
  data: items,
  pagination: {
    current_page: 1,
    total_pages: 1,
    total_items: items.length,
    items_per_page: 25,
    has_next: false,
    has_previous: false,
  },
});

describe('UserManagement page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: adminUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
    vi.mocked(apiClient.get).mockResolvedValue({
      data: makePaginatedUserList(),
    });
  });

  it('renders user list for admin and fetches from /users/admin/users', async () => {
    render(
      <BrowserRouter>
        <UserManagement />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /user management/i })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/users/admin/users',
        expect.objectContaining({
          params: expect.objectContaining({ skip: 0, limit: 10 }),
        })
      );
    });

    // Username from makeAdminUserView() fixture becomes a table cell.
    await waitFor(() =>
      expect(screen.getByText('adminuser')).toBeInTheDocument()
    );
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
  });

  it('debounces the search input and re-fetches with a search param', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <UserManagement />
      </BrowserRouter>
    );

    // Wait for the first fetch to settle.
    await waitFor(() => expect(vi.mocked(apiClient.get)).toHaveBeenCalled());
    vi.mocked(apiClient.get).mockClear();

    const searchInput = screen.getByPlaceholderText(
      /search by username, email, or id/i
    );
    await user.type(searchInput, 'bob');

    // 300ms debounce; waitFor default 1000ms timeout handles it.
    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/users/admin/users',
        expect.objectContaining({
          params: expect.objectContaining({ search: 'bob' }),
        })
      )
    );
  });

  it('opens the edit dialog and calls adminUpdateUser with the form payload', async () => {
    const user = userEvent.setup();
    // Resolve the PUT with the updated user.
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: makeAdminUserView({ username: 'adminuser-updated' }),
    });

    render(
      <BrowserRouter>
        <UserManagement />
      </BrowserRouter>
    );

    // Wait for row to render.
    await waitFor(() =>
      expect(screen.getByText('adminuser')).toBeInTheDocument()
    );

    const editButtons = screen.getAllByRole('button', { name: /^edit$/i });
    await user.click(editButtons[0]!);

    // Dialog renders — the username input is prefilled.
    const usernameInput = await screen.findByLabelText(/^username$/i);
    expect(usernameInput).toHaveValue('adminuser');

    // Click the "Update User" submit button.
    const updateButton = screen.getByRole('button', { name: /update user/i });
    await user.click(updateButton);

    await waitFor(() =>
      expect(vi.mocked(apiClient.put)).toHaveBeenCalledWith(
        `/users/admin/users/${makeAdminUserView().id}`,
        expect.objectContaining({
          username: 'adminuser',
          email: 'admin@example.com',
        })
      )
    );
  });

  it('denies access to authenticated non-admin user', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser, // is_admin: false
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <UserManagement />
      </BrowserRouter>
    );

    expect(
      screen.getByText(/you do not have permission to access user management/i)
    ).toBeInTheDocument();
  });

  it('shows a login prompt when no user is authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <UserManagement />
      </BrowserRouter>
    );

    expect(
      screen.getByText(/please log in to access user management/i)
    ).toBeInTheDocument();
  });
});
