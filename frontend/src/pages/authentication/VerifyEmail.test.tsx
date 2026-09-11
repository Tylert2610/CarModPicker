// VerifyEmail page coverage.
//
// Authenticated-only screen that lets a user who hasn't verified their email
// request a new verification link. Three branches matter:
//   1. No user → "User not found" error + sign-in link.
//   2. email_verified=true → "Email Already Verified" confirmation.
//   3. email_verified=false → "Send Verification Email" button, which goes
//      through `requestVerificationEmail`.
//
// That last one is mocked at `../../api/identityAuth` rather than at the HTTP
// client beneath it: row 13 of docs/identity-adoption.md removed the legacy
// route the page used to post to, and which service is asked for the mail is
// the thing worth pinning, since only the sender can confirm the link it builds.
//
// Authenticated state is constructed from the canonical UserRead mockUser
// (testScenarios.authenticated's user shape is incompatible with UserRead —
// see ExtensionAuth.test.tsx for the same workaround).

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { requestVerificationEmail } from '../../api/identityAuth';
import VerifyEmail from './VerifyEmail';

vi.mock('../../api/identityAuth', () => ({
  requestVerificationEmail: vi.fn(),
}));

describe('VerifyEmail page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows "already verified" state when the user has email_verified=true', () => {
    render(<VerifyEmail />, {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, email_verified: true },
        isLoading: false,
      },
    });
    expect(screen.getByText(/email already verified/i)).toBeInTheDocument();
    expect(
      screen.getByText(/your email address has already been verified/i)
    ).toBeInTheDocument();
  });

  it('shows the send-verification form when email is not yet verified', () => {
    render(<VerifyEmail />, {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, email_verified: false },
        isLoading: false,
      },
    });
    // Page displays user email and a "Send Verification Email" button.
    expect(
      screen.getAllByText(new RegExp(mockUser.email, 'i')).length
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole('button', { name: /send verification email/i })
    ).toBeInTheDocument();
  });

  it('asks the identity service for a mail to the user email on click', async () => {
    vi.mocked(requestVerificationEmail).mockResolvedValueOnce({
      ok: true,
      message: 'Verification email sent.',
    });

    render(<VerifyEmail />, {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, email_verified: false },
        isLoading: false,
      },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /send verification email/i })
    );

    await waitFor(() => {
      expect(requestVerificationEmail).toHaveBeenCalledWith(mockUser.email);
    });

    await waitFor(() => {
      expect(screen.getByText(/verification email sent/i)).toBeInTheDocument();
    });
  });
});
