// The two "mail me a link" routes, across both mechanisms.
//
// These two are worth their own file because they are the pair most easily got
// wrong at cutover, and the failure is invisible until a user clicks a link.
// Whichever service sends the mail also builds the URL inside it and is the
// only one that can confirm the token it carries. Request from one mechanism,
// land the user on the other's confirm page, and the link fails every time
// while both halves look correct in isolation.
//
// So the assertion that matters is not the return value but *which* mechanism
// was asked. Each case pins the call itself.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Stub = Record<string, ReturnType<typeof vi.fn>>;

const post = vi.fn();

/**
 * Loads the module with the identity client either present or absent.
 *
 * `null` is bearer mode, where `getIdentityClient` returns null and the legacy
 * `apiClient` route is the one that must run.
 */
const loadWith = async (stub: Stub | null) => {
  vi.resetModules();
  vi.doMock('./identityClient', () => ({
    getIdentityClient: () => stub,
  }));
  vi.doMock('./client', () => ({
    apiClient: { post },
  }));
  return import('./identityAuth');
};

beforeEach(() => {
  vi.clearAllMocks();
  post.mockResolvedValue({ data: {} });
});

afterEach(() => {
  vi.doUnmock('./identityClient');
  vi.doUnmock('./client');
  vi.resetModules();
});

describe('requestPasswordReset', () => {
  it('asks the identity service when that is the running mechanism', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: true,
      detail: 'If that address has an account, a link is on its way.',
    });
    const { requestPasswordReset } = await loadWith({
      requestPasswordReset: request,
    });

    await expect(requestPasswordReset('user@example.com')).resolves.toEqual({
      ok: true,
      message: 'If that address has an account, a link is on its way.',
    });
    expect(request).toHaveBeenCalledWith({ email: 'user@example.com' });
    // The legacy route must not also have run: two mails, one of which has a
    // link that cannot be confirmed.
    expect(post).not.toHaveBeenCalled();
  });

  it("renders the server's own sentence rather than a local one", async () => {
    // Section 5.4 fixes this wording on the server precisely so that one
    // carefully phrased line is what users see. A local fallback that quietly
    // won would be a regression no type checks.
    const request = vi.fn().mockResolvedValue({
      ok: true,
      detail: 'If that address has an account, a link is on its way.',
    });
    const { requestPasswordReset } = await loadWith({
      requestPasswordReset: request,
    });
    const outcome = await requestPasswordReset('user@example.com');
    expect(outcome.message).toBe(
      'If that address has an account, a link is on its way.'
    );
  });

  it('falls back to a neutral sentence when the server sends no detail', async () => {
    const request = vi.fn().mockResolvedValue({ ok: true });
    const { requestPasswordReset } = await loadWith({
      requestPasswordReset: request,
    });
    const outcome = await requestPasswordReset('user@example.com');
    expect(outcome.ok).toBe(true);
    // Still says nothing about whether the account exists.
    expect(outcome.message).toMatch(/if an account with that email exists/i);
  });

  it('reports a refusal without claiming the mail was sent', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'rate-limited',
      message: 'Too many requests. Try again shortly.',
    });
    const { requestPasswordReset } = await loadWith({
      requestPasswordReset: request,
    });
    await expect(requestPasswordReset('user@example.com')).resolves.toEqual({
      ok: false,
      message: 'Too many requests. Try again shortly.',
    });
  });

  it('uses the legacy route in bearer mode', async () => {
    const { requestPasswordReset } = await loadWith(null);
    const outcome = await requestPasswordReset('user@example.com');
    expect(outcome.ok).toBe(true);
    expect(post).toHaveBeenCalledWith('/auth/reset-password', {
      email: 'user@example.com',
    });
  });
});

describe('requestVerificationEmail', () => {
  it('asks the identity service when that is the running mechanism', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: true,
      detail: 'Verification email sent.',
    });
    const { requestVerificationEmail } = await loadWith({
      requestEmailVerification: request,
    });

    await expect(
      requestVerificationEmail('user@example.com')
    ).resolves.toEqual({
      ok: true,
      message: 'Verification email sent.',
    });
    expect(request).toHaveBeenCalledWith({ email: 'user@example.com' });
    expect(post).not.toHaveBeenCalled();
  });

  it('reports a refusal', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'rate-limited',
      message: 'Too many requests. Try again shortly.',
    });
    const { requestVerificationEmail } = await loadWith({
      requestEmailVerification: request,
    });
    await expect(
      requestVerificationEmail('user@example.com')
    ).resolves.toEqual({
      ok: false,
      message: 'Too many requests. Try again shortly.',
    });
  });

  it('uses the legacy route in bearer mode', async () => {
    const { requestVerificationEmail } = await loadWith(null);
    const outcome = await requestVerificationEmail('user@example.com');
    expect(outcome.ok).toBe(true);
    expect(post).toHaveBeenCalledWith('/auth/verify-email', {
      email: 'user@example.com',
    });
  });
});
