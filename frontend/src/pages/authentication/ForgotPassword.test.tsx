// ForgotPassword page coverage.
//
// Form: single email field, then `requestPasswordReset` from `../../api/identityAuth`,
// then a confirmation alert. The page stopped posting to `apiClient` directly
// when row 13 of docs/identity-adoption.md removed the legacy routes, so the
// seam mocked here is that function rather than the HTTP client underneath it:
// which service sends the mail is exactly what the page must not get wrong, and
// asserting on the call names it.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { requestPasswordReset } from '../../api/identityAuth';
import ForgotPassword from './ForgotPassword';

vi.mock('../../api/identityAuth', () => ({
  requestPasswordReset: vi.fn(),
}));

const submitForm = (email: string) => {
  const emailInput = screen.getByPlaceholderText(/you@example\.com/i);
  fireEvent.change(emailInput, { target: { value: email } });
  const form = emailInput.closest('form');
  if (!form) throw new Error('form not found');
  fireEvent.submit(form);
};

describe('ForgotPassword page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the forgot-password form', () => {
    render(<ForgotPassword />, testScenarios.unauthenticated);
    expect(screen.getByText(/forgot password/i)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/you@example\.com/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /send password reset link/i })
    ).toBeInTheDocument();
  });

  it('submits the email and shows a confirmation message on success', async () => {
    vi.mocked(requestPasswordReset).mockResolvedValueOnce({
      ok: true,
      message:
        'If an account with that email exists, a password reset link has been sent.',
    });

    render(<ForgotPassword />, testScenarios.unauthenticated);
    submitForm('user@example.com');

    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalledWith('user@example.com');
    });

    await waitFor(() => {
      expect(
        screen.getByText(
          /if an account with that email exists, a password reset link has been sent/i
        )
      ).toBeInTheDocument();
    });
  });

  it('rejects an empty email without asking for a mail', async () => {
    render(<ForgotPassword />, testScenarios.unauthenticated);
    submitForm('');

    await waitFor(() => {
      expect(
        screen.getByText(/email address cannot be empty/i)
      ).toBeInTheDocument();
    });
    expect(requestPasswordReset).not.toHaveBeenCalled();
  });
});
