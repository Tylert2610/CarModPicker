// The sign in flows.
//
// Driven through a stubbed `AuthClient` rather than a stubbed `fetch`, because
// what is under test here is the translation from the package's outcome types
// to the union the login page renders, not the wire format. The package has its
// own tests for the wire format.
//
// Row 13 of `docs/identity-adoption.md` deleted the legacy `/api/auth` routes,
// so the bearer mode cases that used to live here are gone with them. What
// replaced them is the null client path below: `getIdentityClient()` returning
// null no longer means "run the other mechanism", it means construction failed,
// and every function has to answer with something a form can render.
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ApiError } from '@webbpulse/api-client';

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
  return import('./identityAuth');
};

/**
 * An `ApiError` carrying the identity envelope.
 *
 * Built through the real constructor with a real envelope body rather than a
 * hand-shaped object, because `getAuthErrorCode` reads the code out of the body
 * through `getWebbPulseError`, which validates the envelope's shape. A stub that
 * merely carried an `error_code` property would take the "not an envelope"
 * branch and every code test would pass for the wrong reason.
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
  vi.resetModules();
});

describe('signIn', () => {
  it('reports authenticated with no user, leaving the fetch to the caller', async () => {
    // No `loadUser` is configured on the client, deliberately: this application
    // reads roughly twenty `UserRead` fields that no token claim carries, and
    // two fetchers for one thing is how the two copies drift. So a successful
    // login carries a null user and the caller follows with `checkAuthStatus`.
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
    // The ticket replaces re-sending the password, and the service never sees
    // the password twice.
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

describe('completeMfa', () => {
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
    // One field and one call. The server tells them apart by shape, so the user
    // never has to pick which kind they are typing.
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

  it('refuses a reissued challenge rather than looping on it', async () => {
    // The server does not reissue a ticket from the second leg, so a second
    // challenge here means something is wrong rather than that the user should
    // be asked for another code.
    const completeTotp = vi.fn().mockResolvedValue({
      mfaRequired: true,
      ticket: 'tkt-2',
      factors: ['totp'],
    });
    const { completeMfa } = await loadWith({ completeTotp });
    const result = await completeMfa(
      { kind: 'identity-ticket', ticket: 'tkt-1', factors: ['totp'] },
      '123456'
    );
    expect(result).toEqual({
      status: 'failed',
      error: 'That code was not accepted.',
    });
  });
});

describe('acceptsRecoveryCodes', () => {
  it('is true, because the identity service is the only issuer left', async () => {
    const { acceptsRecoveryCodes } = await loadWith({});
    expect(acceptsRecoveryCodes()).toBe(true);
  });
});

describe('restoreSession', () => {
  it('reports true when the refresh cookie yielded a token', async () => {
    const initialize = vi.fn().mockResolvedValue(null);
    const getAccessToken = vi.fn().mockReturnValue('fresh-token');
    const { restoreSession } = await loadWith({ initialize, getAccessToken });
    await expect(restoreSession()).resolves.toBe(true);
  });

  it('reports false when there was no session, without throwing', async () => {
    // Arriving signed out is the ordinary case for most page loads, not an
    // error to log or a crash boundary to trip.
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
});

describe('requestVerificationEmail', () => {
  it('prefers the server detail when it sent one', async () => {
    const requestEmailVerification = vi
      .fn()
      .mockResolvedValue({ ok: true, detail: 'Check your inbox.' });
    const { requestVerificationEmail } = await loadWith({
      requestEmailVerification,
    });
    await expect(requestVerificationEmail('a@b.test')).resolves.toEqual({
      ok: true,
      message: 'Check your inbox.',
    });
  });

  it('carries a refusal message through unchanged', async () => {
    const requestEmailVerification = vi
      .fn()
      .mockResolvedValue({ ok: false, message: 'Too many requests.' });
    const { requestVerificationEmail } = await loadWith({
      requestEmailVerification,
    });
    await expect(requestVerificationEmail('a@b.test')).resolves.toEqual({
      ok: false,
      message: 'Too many requests.',
    });
  });
});

describe('requestPasswordReset', () => {
  it('answers the same way whether or not the address has an account', async () => {
    // Deliberate on the server side, and this is the assertion that keeps the
    // client from leaking the difference back out.
    const requestPasswordReset = vi.fn().mockResolvedValue({ ok: true });
    const { requestPasswordReset: request } = await loadWith({
      requestPasswordReset,
    });
    await expect(request('a@b.test')).resolves.toEqual({
      ok: true,
      message:
        'If an account with that email exists, a password reset link has been sent.',
    });
  });
});

// What used to be bearer mode. There is no second mechanism behind these any
// more, so a client that could not be built is a dead end rather than a
// fallback, and each function has to say so in a sentence a form can render.
describe('when the identity client could not be built', () => {
  it('fails the first leg rather than throwing out of the page', async () => {
    const { signIn } = await loadWith(null);
    await expect(signIn('someone@example.test', 'pw')).resolves.toEqual({
      status: 'failed',
      error: 'Sign in is unavailable in this deployment.',
    });
  });

  it('fails the second leg', async () => {
    const { completeMfa } = await loadWith(null);
    await expect(
      completeMfa(
        { kind: 'identity-ticket', ticket: 'tkt-1', factors: ['totp'] },
        '123456'
      )
    ).resolves.toEqual({
      status: 'failed',
      error: 'Two factor sign in is unavailable.',
    });
  });

  it('resolves signOut rather than refusing it', async () => {
    // There is no session to end either, and the caller's next step is to drop
    // its own user state, which is the right thing to do in both cases.
    const { signOut } = await loadWith(null);
    await expect(signOut()).resolves.toBeUndefined();
  });

  it('reports no session to restore', async () => {
    const { restoreSession } = await loadWith(null);
    await expect(restoreSession()).resolves.toBe(false);
  });

  it('refuses a verification email request', async () => {
    const { requestVerificationEmail } = await loadWith(null);
    await expect(requestVerificationEmail('a@b.test')).resolves.toEqual({
      ok: false,
      message: 'Sign in is unavailable in this deployment.',
    });
  });

  it('refuses a password reset request', async () => {
    const { requestPasswordReset } = await loadWith(null);
    await expect(requestPasswordReset('a@b.test')).resolves.toEqual({
      ok: false,
      message: 'Sign in is unavailable in this deployment.',
    });
  });
});
