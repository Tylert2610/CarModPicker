import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import ForgotPassword from './ForgotPassword';

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
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { message: 'Email sent' },
    });

    render(<ForgotPassword />, testScenarios.unauthenticated);
    submitForm('user@example.com');

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
    });
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe(
      '/auth/reset-password'
    );

    const rawBody: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[1];
    const body = rawBody as { email: string };
    expect(body.email).toBe('user@example.com');

    await waitFor(() => {
      expect(
        screen.getByText(
          /if an account with that email exists, a password reset link has been sent/i
        )
      ).toBeInTheDocument();
    });
  });

  it('rejects an empty email without calling the API', async () => {
    render(<ForgotPassword />, testScenarios.unauthenticated);
    submitForm('');

    await waitFor(() => {
      expect(
        screen.getByText(/email address cannot be empty/i)
      ).toBeInTheDocument();
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
