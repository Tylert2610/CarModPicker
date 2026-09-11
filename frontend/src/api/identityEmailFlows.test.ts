// The two "mail me a link" routes.
//
// These two are worth their own file because they were the pair most easily got
// wrong at cutover, and the failure is invisible until a user clicks a link.
// Whichever service sends the mail also builds the URL inside it and is the
// only one that can confirm the token it carries. Row 13 of
// docs/identity-adoption.md removed the other service, so there is no longer a
// mechanism to send the request to by mistake, but the assertion that the
// identity call is the one that runs is still what these cases pin: a
// reintroduced fallback would break links rather than fail a request.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Stub = Record<string, ReturnType<typeof vi.fn>>;

const post = vi.fn();

/**
 * Loads the module with the identity client either present or absent.
 *
 * `null` now means construction failed rather than "run the other mechanism":
 * see the doc comment on `getIdentityClient` in `./identityClient`. `apiClient`
 * is still stubbed so that a request escaping to it would be caught rather than
 * hitting the network.
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

  it('refuses rather than falling back when the client is missing', async () => {
    // There is no `/auth/reset-password` behind this any more. Sending the mail
    // some other way would mean a link nothing can confirm, so the honest
    // answer is to say no mail was sent.
    const { requestPasswordReset } = await loadWith(null);
    const outcome = await requestPasswordReset('user@example.com');
    expect(outcome.ok).toBe(false);
    expect(post).not.toHaveBeenCalled();
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

    await expect(requestVerificationEmail('user@example.com')).resolves.toEqual(
      {
        ok: true,
        message: 'Verification email sent.',
      }
    );
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
    await expect(requestVerificationEmail('user@example.com')).resolves.toEqual(
      {
        ok: false,
        message: 'Too many requests. Try again shortly.',
      }
    );
  });

  it('refuses rather than falling back when the client is missing', async () => {
    const { requestVerificationEmail } = await loadWith(null);
    const outcome = await requestVerificationEmail('user@example.com');
    expect(outcome.ok).toBe(false);
    expect(post).not.toHaveBeenCalled();
  });
});
