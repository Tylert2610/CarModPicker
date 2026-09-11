import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ApiClientResponse } from '../api/client';
import { buildApiError, buildResponse } from '../test/apiResponse';
import { useGoogleSignIn } from './useGoogleSignIn';
import { authApi } from '../api/auth';
import type { UserRead } from '../types/Api';
import { mockUser } from '../test/mocks/api';

vi.mock('../api/auth', async () => {
  const actual =
    await vi.importActual<typeof import('../api/auth')>('../api/auth');
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      googleSignIn: vi.fn(),
    },
  };
});

function buildGoogleResponse<T>(data: T): ApiClientResponse<T> {
  return buildResponse(data);
}

describe('useGoogleSignIn — env gate documentation', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  it('tolerates VITE_GOOGLE_CLIENT_ID being empty at runtime', () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '');
    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn: vi.fn(), onError: vi.fn() })
    );
    expect(result.current.state).toEqual({ kind: 'idle' });
  });

  it('tolerates VITE_GOOGLE_CLIENT_ID being set at runtime', () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'client-id-123');
    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn: vi.fn(), onError: vi.fn() })
    );
    expect(result.current.state).toEqual({ kind: 'idle' });
  });
});

describe('useGoogleSignIn', () => {
  const onLoggedIn = vi.fn();
  const onError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts in idle state with a 64-hex-char nonce', () => {
    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn, onError })
    );

    expect(result.current.state).toEqual({ kind: 'idle' });
    expect(typeof result.current.nonce).toBe('string');
    expect(result.current.nonce).toMatch(/^[0-9a-f]{64}$/);
  });

  it('calls onLoggedIn and returns to idle when server returns an access_token', async () => {
    const user: UserRead = mockUser;
    vi.mocked(authApi.googleSignIn).mockResolvedValueOnce(
      buildGoogleResponse({
        access_token: 'tok',
        token_type: 'bearer',
        user,
      })
    );

    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn, onError })
    );

    await act(async () => {
      await result.current.submitCredential('id-token-abc');
    });

    await waitFor(() => {
      expect(onLoggedIn).toHaveBeenCalledWith(user);
    });
    expect(result.current.state).toEqual({ kind: 'idle' });
    expect(onError).not.toHaveBeenCalled();
  });

  it('routes to signup state when server requires_signup', async () => {
    vi.mocked(authApi.googleSignIn).mockResolvedValueOnce(
      buildGoogleResponse({
        requires_signup: true,
        signup_token: 'signup-token',
        suggested_username: 'newuser',
        email: 'x@example.com',
      })
    );

    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn, onError })
    );

    await act(async () => {
      await result.current.submitCredential('id-token-signup');
    });

    expect(result.current.state.kind).toBe('signup');
    expect(onLoggedIn).not.toHaveBeenCalled();
  });

  it('calls onError and returns to idle when authApi.googleSignIn rejects', async () => {
    vi.mocked(authApi.googleSignIn).mockRejectedValueOnce(
      buildApiError(401, {
        success: false,
        status: 401,
        message: 'Google sign-in failed.',
        request_id: 'req-1',
        error_code: 'UNAUTHORIZED',
      })
    );

    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn, onError })
    );

    await act(async () => {
      await result.current.submitCredential('bad-token');
    });

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Google sign-in failed.');
    });
    expect(result.current.state).toEqual({ kind: 'idle' });
  });

  it('reset() returns state to idle', () => {
    const { result } = renderHook(() =>
      useGoogleSignIn({ onLoggedIn, onError })
    );

    act(() => {
      result.current.reset();
    });

    expect(result.current.state).toEqual({ kind: 'idle' });
  });
});
