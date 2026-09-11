import { describe, it, expect } from 'vitest';
import { render, screen, testScenarios } from '../../test/utils/test-utils';
import VerifyEmailConfirm from './VerifyEmailConfirm';

describe('VerifyEmailConfirm page', () => {
  it('shows the success message when ?status=success is set via token=abc path', () => {
    render(<VerifyEmailConfirm />, {
      ...testScenarios.unauthenticated,
      route:
        '/verify-email/confirm?token=abc&status=success&message=Email+verified',
    });
    expect(screen.getByText(/email verification result/i)).toBeInTheDocument();
    expect(screen.getByText(/email verified/i)).toBeInTheDocument();
  });

  it('shows the error message when ?status=error is set with a token in the URL', () => {
    render(<VerifyEmailConfirm />, {
      ...testScenarios.unauthenticated,
      route:
        '/verify-email/confirm?token=abc&status=error&message=Token+expired',
    });
    expect(screen.getByText(/token expired/i)).toBeInTheDocument();
  });

  it('shows the invalid-link fallback when no status param is provided', () => {
    render(<VerifyEmailConfirm />, {
      ...testScenarios.unauthenticated,
      route: '/verify-email/confirm',
    });
    expect(
      screen.getByText(
        /invalid or missing verification link|request a new verification email/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /verification email/i })
    ).toBeInTheDocument();
  });
});
