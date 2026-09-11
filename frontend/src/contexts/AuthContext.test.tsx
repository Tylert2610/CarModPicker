import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@webbpulse/api-client';
import { buildApiError } from '../test/apiResponse';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';

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

vi.mock('../api/auth', async () => {
  const actual =
    await vi.importActual<typeof import('../api/auth')>('../api/auth');
  return {
    ...actual,
    authApi: { logout: mockLogout },
  };
});

vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: mockRemoveStoredToken,
  isApiErrorWithStatus: (error: unknown): error is ApiError =>
    error instanceof ApiError,
}));

vi.mock('@sentry/react', () => ({
  setUser: vi.fn(),
}));

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
    expect(mockRemoveStoredToken).not.toHaveBeenCalled();
  });

  it('flips state to authenticated when login() is called directly', async () => {
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

    expect(mockRemoveStoredToken).toHaveBeenCalled();
  });
});
