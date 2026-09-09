// Phase 8 Plan 10 (D-11 Wave 3) — ForgotPasswordConfirm page coverage.
//
// Reads ?token=... from the URL via useSearchParams. If token is absent the
// page shows an error + "Request new reset link" CTA. If token is present the
// form accepts a new password + confirmation and posts via
// authApi.resetPasswordConfirm(token, { password }).

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import ForgotPasswordConfirm from './ForgotPasswordConfirm';

describe('ForgotPasswordConfirm page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the password-reset form when a token is present (?token=abc)', () => {
    render(<ForgotPasswordConfirm />, {
      ...testScenarios.unauthenticated,
      route: '/reset-password/confirm?token=abc',
    });
    // The phrase "Set new password" appears twice: once as the card title
    // and once as the submit button label. Assert at least one match.
    expect(screen.getAllByText(/set new password/i).length).toBeGreaterThan(0);
    expect(screen.getByPlaceholderText(/^new password$/i)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/confirm new password/i)
    ).toBeInTheDocument();
  });

  it('POSTs the new password to /auth/reset-password/confirm with the URL token', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { message: 'Password updated' },
    });

    render(<ForgotPasswordConfirm />, {
      ...testScenarios.unauthenticated,
      route: '/reset-password/confirm?token=abc',
    });

    const newPw = screen.getByPlaceholderText(/^new password$/i);
    const confirmPw = screen.getByPlaceholderText(/confirm new password/i);
    fireEvent.change(newPw, { target: { value: 'newpassword123' } });
    fireEvent.change(confirmPw, { target: { value: 'newpassword123' } });
    const form = newPw.closest('form');
    if (!form) throw new Error('form not found');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
    });
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe(
      '/auth/reset-password/confirm'
    );
    const rawBody: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[1];
    const body = rawBody as {
      token: string;
      new_password: { password: string };
    };
    expect(body.token).toBe('abc');
    expect(body.new_password.password).toBe('newpassword123');
  });

  it('shows a "no reset token" error when token is missing from the URL', async () => {
    render(<ForgotPasswordConfirm />, {
      ...testScenarios.unauthenticated,
      route: '/reset-password/confirm',
    });
    // Page surfaces the "no reset token" copy and a link to request a new
    // reset. Both confirm we're in the error branch.
    await waitFor(() => {
      expect(screen.getByText(/no reset token found/i)).toBeInTheDocument();
    });
    expect(
      screen.getByRole('link', { name: /new reset link/i })
    ).toBeInTheDocument();
  });
});
