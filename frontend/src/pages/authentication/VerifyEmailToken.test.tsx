// The mailed verification link branch of /verify-email.
//
// The component takes its client from `getIdentityClient`, so mocking that one
// module is what drives every branch here, including the bearer-mode case where
// it returns null.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '../../test/utils/test-utils';

const confirmEmailVerification = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () => (clientIsNull ? null : { confirmEmailVerification }),
  identityOriginFrom: (v: string) => v,
  resetIdentityClientForTests: () => undefined,
}));

import VerifyEmailToken from './VerifyEmailToken';

/**
 * Puts a token in the URL the way a mailed link would.
 *
 * Relative rather than absolute, because `readLinkToken` checks the path
 * against `VERIFY_EMAIL_PATH` and jsdom refuses a `replaceState` that changes
 * the origin.
 */
const arriveWithToken = (token: string | null) => {
  window.history.replaceState(
    {},
    '',
    token === null ? '/verify-email' : `/verify-email?token=${token}`
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
  arriveWithToken('tok-1');
});

describe('VerifyEmailToken', () => {
  it('confirms the token and reports success', async () => {
    confirmEmailVerification.mockResolvedValue({ ok: true });
    render(<VerifyEmailToken />);
    expect(await screen.findByText(/email verified/i)).toBeInTheDocument();
    expect(confirmEmailVerification).toHaveBeenCalledWith({ token: 'tok-1' });
  });

  it('spends the token exactly once across a strict mode double mount', async () => {
    // The bug this guard exists for: the second run of a mount effect would
    // present an already spent token, and the user would be told their link was
    // invalid on the one page whose job is to tell them it worked.
    confirmEmailVerification.mockResolvedValue({ ok: true });
    const { rerender } = render(<VerifyEmailToken />);
    rerender(<VerifyEmailToken />);
    await screen.findByText(/email verified/i);
    expect(confirmEmailVerification).toHaveBeenCalledTimes(1);
  });

  it('names the next step when the link is spent or expired', async () => {
    confirmEmailVerification.mockResolvedValue({
      ok: false,
      reason: 'invalid-link',
      message: '',
    });
    render(<VerifyEmailToken />);
    // The fallback rather than a bare "invalid": a user holding a dead link
    // needs to know to request another one.
    expect(
      await screen.findByText(/sign in and request a new one/i)
    ).toBeInTheDocument();
  });

  it('prefers the server own message over the fallback', async () => {
    // The server's wording is written to be shown, so it wins whenever there
    // is one.
    confirmEmailVerification.mockResolvedValue({
      ok: false,
      reason: 'invalid-link',
      message: 'This link was issued for a different account.',
    });
    render(<VerifyEmailToken />);
    expect(
      await screen.findByText(/issued for a different account/i)
    ).toBeInTheDocument();
  });

  it('explains a rate limited refusal', async () => {
    confirmEmailVerification.mockResolvedValue({
      ok: false,
      reason: 'rate-limited',
      message: '',
    });
    render(<VerifyEmailToken />);
    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
  });

  it('reports a missing token rather than calling the server', async () => {
    arriveWithToken(null);
    render(<VerifyEmailToken />);
    expect(await screen.findByText(/missing its token/i)).toBeInTheDocument();
    expect(confirmEmailVerification).not.toHaveBeenCalled();
  });

  it('survives a network failure with a retryable message', async () => {
    confirmEmailVerification.mockRejectedValue(new Error('offline'));
    render(<VerifyEmailToken />);
    expect(
      await screen.findByText(/check your connection/i)
    ).toBeInTheDocument();
  });

  it('says verification is unavailable in bearer mode', async () => {
    // The page is registered unconditionally so the route coverage test can see
    // it, which means it can be reached in a bearer bundle. It says so rather
    // than throwing on a null client.
    clientIsNull = true;
    render(<VerifyEmailToken />);
    expect(
      await screen.findByText(/not available in this deployment/i)
    ).toBeInTheDocument();
    expect(confirmEmailVerification).not.toHaveBeenCalled();
  });
});
