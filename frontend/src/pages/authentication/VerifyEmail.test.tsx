import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { apiClient } from '../../api/client';
import VerifyEmail from './VerifyEmail';

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
    expect(
      screen.getAllByText(new RegExp(mockUser.email, 'i')).length
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole('button', { name: /send verification email/i })
    ).toBeInTheDocument();
  });

  it('POSTs to /auth/verify-email with the user email when the button is clicked', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} });

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
      expect(apiClient.post).toHaveBeenCalled();
    });
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe(
      '/auth/verify-email'
    );
    const rawBody: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[1];
    const body = rawBody as { email: string };
    expect(body.email).toBe(mockUser.email);

    await waitFor(() => {
      expect(screen.getByText(/verification email sent/i)).toBeInTheDocument();
    });
  });
});
