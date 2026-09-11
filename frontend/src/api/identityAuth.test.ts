import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ApiError } from '@webbpulse/api-client';
import { apiClient } from './client';

/** A stand-in for the one method a given test drives. */
type Stub = Record<string, ReturnType<typeof vi.fn>>;

/** Loads `identityAuth` with `getIdentityClient` returning `stub`, or null. */
const loadWith = async (stub: Stub | null) => {
  vi.resetModules();
  vi.doMock('./identityClient', () => ({
    getIdentityClient: () => stub,
    identityOriginFrom: (v: string) => v,
    resetIdentityClientForTests: () => undefined,
  }));
  vi.doMock('./authMode', async (importOriginal) => {
    const actual = await importOriginal<typeof import('./authMode')>();
    return { ...actual, AUTH_MODE: stub === null ? 'bearer' : 'identity' };
  });
  return import('./identityAuth');
};

/**
 * An `ApiError` carrying a real identity envelope. A hand-shaped stub would
 * fail the envelope validation and pass every code test for the wrong reason.
 */
const identityError = (status: number, code: string, message: string) =>
  new ApiError({
    status,
    statusText: '',
    url: 'https://api.test/api/auth/login',
    method: 'POST',
    body: {
      success: false,
      status,
      message,
      request_id: 'req-1',
      error_code: code,
    },
  });

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.doUnmock('./identityClient');
  vi.doUnmock('./authMode');
  vi.resetModules();
});

describe('signIn in identity mode', () => {
  it('reports authenticated with no user, leaving the fetch to the caller', async () => {
    const login = vi.fn().mockResolvedValue({ mfaRequired: false, user: null });
    const { signIn } = await loadWith({ login });
    await expect(signIn('someone@example.test', 'pw')).resolves.toEqual({
      status: 'authenticated',
      user: null,
    });
    expect(login).toHaveBeenCalledWith({
      email: 'someone@example.test',
      password: 'pw',
    });
  });

  it('carries the server ticket back for the second leg', async () => {
    const login = vi.fn().mockResolvedValue({
      mfaRequired: true,
      ticket: 'tkt-1',
      factors: ['totp'],
    });
    const { signIn } = await loadWith({ login });
    await expect(signIn('someone@example.test', 'pw')).resolves.toEqual({
      status: 'mfa-required',
      challenge: {
        kind: 'identity-ticket',
        ticket: 'tkt-1',
        factors: ['totp'],
      },
    });
  });

  it('turns bad credentials into a sentence rather than a throw', async () => {
    const login = vi
      .fn()
      .mockRejectedValue(identityError(401, 'INVALID_CREDENTIALS', 'no'));
    const { signIn } = await loadWith({ login });
    const result = await signIn('someone@example.test', 'wrong');
    expect(result.status).toBe('failed');
    expect(result).toHaveProperty('error', 'Incorrect email or password.');
  });

  it('names email verification as the next step when that is the refusal', async () => {
    const login = vi
      .fn()
      .mockRejectedValue(identityError(403, 'EMAIL_NOT_VERIFIED', 'no'));
    const { signIn } = await loadWith({ login });
    const result = await signIn('someone@example.test', 'pw');
    expect(result).toHaveProperty(
      'error',
      'Verify your email address before signing in.'
    );
  });

  it('falls back to a generic sentence for an unmodelled failure', async () => {
    const login = vi.fn().mockRejectedValue(new Error('socket hang up'));
    const { signIn } = await loadWith({ login });
    const result = await signIn('someone@example.test', 'pw');
    expect(result.status).toBe('failed');
  });
});

describe('completeMfa in identity mode', () => {
  it('spends the ticket with the code', async () => {
    const completeTotp = vi
      .fn()
      .mockResolvedValue({ mfaRequired: false, user: null });
    const { completeMfa } = await loadWith({ completeTotp });
    const result = await completeMfa(
      { kind: 'identity-ticket', ticket: 'tkt-1', factors: ['totp'] },
      '123456'
    );
    expect(result).toEqual({ status: 'authenticated', user: null });
    expect(completeTotp).toHaveBeenCalledWith({
      ticket: 'tkt-1',
      code: '123456',
    });
  });

  it('sends a recovery code down the same path as a TOTP code', async () => {
    const completeTotp = vi
      .fn()
      .mockResolvedValue({ mfaRequired: false, user: null });
    const { completeMfa } = await loadWith({ completeTotp });
    await completeMfa(
      { kind: 'identity-ticket', ticket: 'tkt-1', factors: ['totp'] },
      'abcd-efgh-ijkl'
    );
    expect(completeTotp).toHaveBeenCalledWith({
      ticket: 'tkt-1',
      code: 'abcd-efgh-ijkl',
    });
  });

  it('reports a refused code without looping', async () => {
    const completeTotp = vi
      .fn()
      .mockRejectedValue(identityError(401, 'INVALID_MFA_CODE', 'nope'));
    const { completeMfa } = await loadWith({ completeTotp });
    const result = await completeMfa(
      { kind: 'identity-ticket', ticket: 'tkt-1', factors: ['totp'] },
      '000000'
    );
    expect(result.status).toBe('failed');
  });

  it('reports an expired ticket as a failure', async () => {
    const completeTotp = vi
      .fn()
      .mockRejectedValue(identityError(401, 'MFA_TICKET_INVALID', 'expired'));
    const { completeMfa } = await loadWith({ completeTotp });
    const result = await completeMfa(
      { kind: 'identity-ticket', ticket: 'stale', factors: ['totp'] },
      '123456'
    );
    expect(result.status).toBe('failed');
  });
});

describe('bearer mode is unchanged', () => {
  it('sends the legacy credentials and returns the user from the body', async () => {
    const user = { id: 'u1', username: 'someone' };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { access_token: 'tok', token_type: 'bearer', user },
    });
    const { signIn } = await loadWith(null);
    const result = await signIn('someone', 'pw');
    expect(result).toEqual({ status: 'authenticated', user });
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe('/auth/token');
  });

  it('carries the credentials forward as the challenge', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { requires_2fa: true },
    });
    const { signIn } = await loadWith(null);
    await expect(signIn('someone', 'pw')).resolves.toEqual({
      status: 'mfa-required',
      challenge: {
        kind: 'legacy-credentials',
        username: 'someone',
        password: 'pw',
      },
    });
  });

  it('sends the code as otp on the legacy second leg', async () => {
    const user = { id: 'u1', username: 'someone' };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { access_token: 'tok', token_type: 'bearer', user },
    });
    const { completeMfa } = await loadWith(null);
    const result = await completeMfa(
      { kind: 'legacy-credentials', username: 'someone', password: 'pw' },
      '123456'
    );
    expect(result).toEqual({ status: 'authenticated', user });
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[1]).toEqual({
      username: 'someone',
      password: 'pw',
      otp: '123456',
    });
  });

  it('does not accept recovery codes', async () => {
    const { acceptsRecoveryCodes } = await loadWith(null);
    expect(acceptsRecoveryCodes()).toBe(false);
  });

  it('accepts recovery codes in identity mode', async () => {
    const { acceptsRecoveryCodes } = await loadWith({});
    expect(acceptsRecoveryCodes()).toBe(true);
  });
});

describe('restoreSession', () => {
  it('is a no-op in bearer mode', async () => {
    const { restoreSession } = await loadWith(null);
    await expect(restoreSession()).resolves.toBe(false);
  });

  it('reports true when the refresh cookie yielded a token', async () => {
    const initialize = vi.fn().mockResolvedValue(null);
    const getAccessToken = vi.fn().mockReturnValue('fresh-token');
    const { restoreSession } = await loadWith({ initialize, getAccessToken });
    await expect(restoreSession()).resolves.toBe(true);
  });

  it('reports false when there was no session, without throwing', async () => {
    const initialize = vi.fn().mockRejectedValue(new Error('no session'));
    const getAccessToken = vi.fn().mockReturnValue(null);
    const { restoreSession } = await loadWith({ initialize, getAccessToken });
    await expect(restoreSession()).resolves.toBe(false);
  });

  it('reports false when initialize resolved but left no token', async () => {
    const initialize = vi.fn().mockResolvedValue(null);
    const getAccessToken = vi.fn().mockReturnValue(null);
    const { restoreSession } = await loadWith({ initialize, getAccessToken });
    await expect(restoreSession()).resolves.toBe(false);
  });
});

describe('signOut', () => {
  it('calls the identity logout, which clears the httpOnly cookie', async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    const { signOut } = await loadWith({ logout });
    await signOut();
    expect(logout).toHaveBeenCalled();
  });

  it('calls the legacy logout in bearer mode', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} });
    const { signOut } = await loadWith(null);
    await signOut();
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe('/auth/logout');
  });
});
