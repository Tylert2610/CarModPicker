// Phase 8 plan 08-09 (D-10) — provider test for AuthContext.
//
// Covers the provider-internal state transitions that the useAuth hook tests
// (plan 08-08) cannot exercise: the checkAuthStatus useEffect on mount, the
// authenticated-on-mount success path, the 401-on-mount invalid-token path,
// the login() transition, and the logout() transition.
//
// Per PATTERNS.md §10 + Gotcha #3: AuthProvider calls useNavigate() at render,
// so every test MUST wrap in <MemoryRouter>.
//
// Per Gotcha #8 + PATTERNS.md: test-utils.tsx customRender silently mocks
// `../../hooks/useAuth`. This test does NOT use customRender — it calls the
// bare `render` from @testing-library/react so AuthProvider wires up the REAL
// context, and our in-file <Consumer> exercises it through useContext.
//
// AuthContext imports `authApi` from `../api/auth` and `apiClient` /
// `removeStoredToken` from `../api/client`. This file mocks both directly so
// it can assert on the logout and token-clearing calls.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@webbpulse/api-client';
import { buildApiError } from '../test/apiResponse';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';

// Hoisted mocks so the vi.mock factory can close over them.
const { mockApiClient, mockLogout, mockRemoveStoredToken } = vi.hoisted(() => ({
  mockApiClient: {
    get: vi.fn().mockResolvedValue({ data: null }),
    post: vi.fn().mockResolvedValue({ data: null }),
    put: vi.fn().mockResolvedValue({ data: null }),
    delete: vi.fn().mockResolvedValue({ data: null }),
    patch: vi.fn().mockResolvedValue({ data: null }),
  },
  mockLogout: vi.fn(),
  mockRemoveStoredToken: vi.fn(),
}));

// AuthContext.tsx imports `apiClient` and `removeStoredToken` from
// `../api/client` (already mocked globally by setup.ts) and `authApi` from
// `../api/auth`. Override the two named exports whose calls this file asserts
// on with our hoisted vi.fn()s, leaving the rest of each module intact.
vi.mock('../api/auth', async () => {
  const actual =
    await vi.importActual<typeof import('../api/auth')>('../api/auth');
  return {
    ...actual,
    authApi: { logout: mockLogout },
  };
});

// setup.ts mocks `../api/client` wholesale, so a file-level mock replaces it
// rather than merging. Re-declare the same shape here, binding
// `removeStoredToken` to the hoisted spy this file asserts on and keeping the
// same mocked Axios surface so no request escapes to the network.
vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: mockRemoveStoredToken,
  // The real predicate: it does no I/O, and stubbing it would make the 401
  // branch below unreachable no matter what the request rejected with.
  isApiErrorWithStatus: (error: unknown): error is ApiError =>
    error instanceof ApiError,
}));

// Silence Sentry.setUser — AuthContext calls it unconditionally on every user
// change. Namespace import (`import * as Sentry`) only needs `setUser`.
vi.mock('@sentry/react', () => ({
  setUser: vi.fn(),
}));

// Import the provider AFTER the vi.mock declarations (hoisted, but explicit
// here for readers).
import { AuthProvider } from './AuthContext';
import { useAuth } from '../hooks/useAuth';

function Consumer() {
  const { isAuthenticated, user, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="state">
        {isAuthenticated ? (user?.username ?? 'authed-noname') : 'anon'}
      </span>
      <span data-testid="loading">{isLoading ? 'loading' : 'idle'}</span>
      <button type="button" onClick={() => login(mockUser)}>
        login-direct
      </button>
      <button
        type="button"
        onClick={() => {
          logout();
        }}
      >
        logout
      </button>
    </div>
  );
}

function renderWithProvider(children: ReactNode = <Consumer />) {
  return render(
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

describe('AuthContext provider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset per-test mock behavior — each test redeclares the promises it needs.
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.post).mockReset();
    mockLogout.mockReset();
    mockRemoveStoredToken.mockReset();
  });

  it('authenticates on mount when /users/me resolves with a user', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockUser });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith('/users/me');
    expect(screen.getByTestId('loading').textContent).toBe('idle');
  });

  it('stays unauthenticated when /users/me returns 401 and clears the stored token', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(
      buildApiError(401, {
        success: false,
        status: 401,
        message: 'Not authenticated',
        request_id: 'req-401',
      })
    );

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('idle')
    );

    expect(screen.getByTestId('state').textContent).toBe('anon');
    expect(mockRemoveStoredToken).toHaveBeenCalledTimes(1);
  });

  it('stays unauthenticated when /users/me resolves with null data (no token)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: null });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('idle')
    );

    expect(screen.getByTestId('state').textContent).toBe('anon');
    // Resolve path — no invalid-token removal, unlike the 401 path.
    expect(mockRemoveStoredToken).not.toHaveBeenCalled();
  });

  it('flips state to authenticated when login() is called directly', async () => {
    // Initial mount: no auth.
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: null });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );

    fireEvent.click(screen.getByText('login-direct'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );
  });

  it('flips state from authenticated to unauthenticated on logout and calls authApi.logout', async () => {
    // Mount authenticated.
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockUser });
    mockLogout.mockResolvedValueOnce({ data: { message: 'Logged out' } });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    fireEvent.click(screen.getByText('logout'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );

    expect(mockLogout).toHaveBeenCalledTimes(1);
    // Loading should settle back to idle after the logout finally-block runs.
    expect(screen.getByTestId('loading').textContent).toBe('idle');
  });

  it('still clears auth state when authApi.logout rejects', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockUser });
    mockLogout.mockRejectedValueOnce(new Error('network down'));

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    fireEvent.click(screen.getByText('logout'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );

    // When authApi.logout throws, the catch branch calls removeStoredToken
    // before the finally-block resets user state.
    expect(mockRemoveStoredToken).toHaveBeenCalled();
  });
});
