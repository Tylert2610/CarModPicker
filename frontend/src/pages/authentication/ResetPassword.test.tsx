// The /reset-password landing page for identity mode reset links.
//
// The behaviour worth pinning is that the local checks run before the token is
// spent: it is single use, so a mismatched confirmation field must not consume
// it on an attempt that could never have succeeded.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '../../test/utils/test-utils';

const confirmPasswordReset = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () => (clientIsNull ? null : { confirmPasswordReset }),
  identityOriginFrom: (v: string) => v,
  resetIdentityClientForTests: () => undefined,
}));

import ResetPassword from './ResetPassword';

/**
 * Puts a token in the URL the way a mailed link would.
 *
 * Relative rather than absolute: `readLinkToken` checks the path against
 * `RESET_PASSWORD_PATH`, and jsdom refuses a `replaceState` across origins.
 */
const arriveWithToken = (token: string | null) => {
  window.history.replaceState(
    {},
    '',
    token === null ? '/reset-password' : `/reset-password?token=${token}`
  );
};

/** Fills both password fields and submits. */
const submitPasswords = (first: string, second: string) => {
  fireEvent.change(screen.getByLabelText(/^new password$/i), {
    target: { value: first },
  });
  fireEvent.change(screen.getByLabelText(/confirm new password/i), {
    target: { value: second },
  });
  fireEvent.click(screen.getByRole('button', { name: /set new password/i }));
};

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
  arriveWithToken('tok-1');
});

describe('ResetPassword', () => {
  it('sends the token with the new password and confirms the change', async () => {
    confirmPasswordReset.mockResolvedValue({ ok: true });
    render(<ResetPassword />);
    submitPasswords('a-good-password', 'a-good-password');
    expect(
      await screen.findByText(/every other session has been signed out/i)
    ).toBeInTheDocument();
    expect(confirmPasswordReset).toHaveBeenCalledWith({
      token: 'tok-1',
      newPassword: 'a-good-password',
    });
  });

  it('does not spend the token when the two fields disagree', async () => {
    // The point of checking locally. The token survives, so the user can fix
    // the typo and submit the same link again.
    render(<ResetPassword />);
    submitPasswords('a-good-password', 'a-typo');
    expect(
      await screen.findByText(/passwords don't match/i)
    ).toBeInTheDocument();
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it('does not spend the token on an empty password', async () => {
    render(<ResetPassword />);
    submitPasswords('   ', '   ');
    expect(
      await screen.findByText(/password cannot be empty/i)
    ).toBeInTheDocument();
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it('separates a rejected password from a dead link', async () => {
    // Two different remedies. Only one of them is the user's own doing.
    confirmPasswordReset.mockResolvedValue({
      ok: false,
      reason: 'password-rejected',
      message: '',
    });
    render(<ResetPassword />);
    submitPasswords('password', 'password');
    expect(
      await screen.findByText(/longer or less common one/i)
    ).toBeInTheDocument();
  });

  it('names the next step when the link is spent or expired', async () => {
    confirmPasswordReset.mockResolvedValue({
      ok: false,
      reason: 'invalid-link',
      message: '',
    });
    render(<ResetPassword />);
    submitPasswords('a-good-password', 'a-good-password');
    expect(
      await screen.findByText(/reset links expire and can only be used once/i)
    ).toBeInTheDocument();
  });

  it('prefers the server own message over the fallback', async () => {
    confirmPasswordReset.mockResolvedValue({
      ok: false,
      reason: 'invalid-link',
      message: 'That link belongs to a different account.',
    });
    render(<ResetPassword />);
    submitPasswords('a-good-password', 'a-good-password');
    expect(
      await screen.findByText(/belongs to a different account/i)
    ).toBeInTheDocument();
  });

  it('survives a network failure with a retryable message', async () => {
    confirmPasswordReset.mockRejectedValue(new Error('offline'));
    render(<ResetPassword />);
    submitPasswords('a-good-password', 'a-good-password');
    expect(
      await screen.findByText(/check your connection/i)
    ).toBeInTheDocument();
  });

  it('re-enables the form after a failure so the user can retry', async () => {
    confirmPasswordReset.mockRejectedValue(new Error('offline'));
    render(<ResetPassword />);
    submitPasswords('a-good-password', 'a-good-password');
    await screen.findByText(/check your connection/i);
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /set new password/i })
      ).not.toBeDisabled();
    });
  });

  it('asks for a new link when the URL carries no token', () => {
    arriveWithToken(null);
    render(<ResetPassword />);
    expect(screen.getByText(/no reset token found/i)).toBeInTheDocument();
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it('says password reset is unavailable in bearer mode', () => {
    // The route is registered unconditionally so the route coverage test can
    // see it, which means a bearer bundle can reach it. CarModPicker's own
    // reset link lands on /forgot-password/confirm and still works.
    clientIsNull = true;
    render(<ResetPassword />);
    expect(
      screen.getByText(/not available in this deployment/i)
    ).toBeInTheDocument();
  });
});
