/**
 * Sign in and sign out in one shape for both the legacy bearer flow and the
 * identity service, so pages render a result without knowing which ran. An MFA
 * challenge is a successful outcome here, not a thrown error.
 */
import { describeAuthError, getAuthErrorCode } from '@webbpulse/auth';
import { AUTH_MODE } from './authMode';
import { getIdentityClient } from './identityClient';
import { authApi } from './auth';
import { apiClient } from './client';
import type { UserRead } from '../types/Api';
import { getApiErrorMessage } from '../utils/apiError';

/**
 * Opaque carrier for the second sign in leg: a server ticket in identity mode,
 * the credentials in bearer mode, so the login form needs no mode branch.
 */
export type LoginChallenge =
  | { kind: 'identity-ticket'; ticket: string; factors: string[] }
  | { kind: 'legacy-credentials'; username: string; password: string };

/** What a sign in attempt produced. */
export type LoginResult =
  | { status: 'authenticated'; user: UserRead | null }
  | { status: 'mfa-required'; challenge: LoginChallenge }
  | { status: 'failed'; error: string };

/**
 * True when the code field should also accept a recovery code, which only the
 * identity service issues. A function so tests can drive both modes.
 */
export const acceptsRecoveryCodes = (): boolean => AUTH_MODE === 'identity';

/**
 * Runs the first leg of a sign in. Returns no user in identity mode, so the
 * caller follows a success with `checkAuthStatus()` in both modes.
 */
export const signIn = async (
  username: string,
  password: string
): Promise<LoginResult> => {
  const identity = getIdentityClient();
  if (identity !== null) {
    try {
      const outcome = await identity.login({ email: username, password });
      if (outcome.mfaRequired) {
        return {
          status: 'mfa-required',
          challenge: {
            kind: 'identity-ticket',
            ticket: outcome.ticket,
            factors: outcome.factors,
          },
        };
      }
      return { status: 'authenticated', user: null };
    } catch (error) {
      return { status: 'failed', error: describeIdentityFailure(error) };
    }
  }

  try {
    const response = await authApi.login({ username, password });
    const body = response.data;
    if ('requires_2fa' in body && body.requires_2fa === true) {
      return {
        status: 'mfa-required',
        challenge: { kind: 'legacy-credentials', username, password },
      };
    }
    return { status: 'authenticated', user: body as UserRead };
  } catch (error) {
    return {
      status: 'failed',
      error: getApiErrorMessage(error, 'Sign in failed. Please try again.'),
    };
  }
};

/**
 * Runs the second leg with a TOTP code or, in identity mode, a recovery code.
 * The server tells them apart, so the form needs one field rather than a choice.
 */
export const completeMfa = async (
  challenge: LoginChallenge,
  code: string
): Promise<LoginResult> => {
  if (challenge.kind === 'identity-ticket') {
    const identity = getIdentityClient();
    if (identity === null) {
      return { status: 'failed', error: 'Two factor sign in is unavailable.' };
    }
    try {
      const outcome = await identity.completeTotp({
        ticket: challenge.ticket,
        code,
      });
      if (outcome.mfaRequired) {
        return { status: 'failed', error: 'That code was not accepted.' };
      }
      return { status: 'authenticated', user: null };
    } catch (error) {
      return { status: 'failed', error: describeIdentityFailure(error) };
    }
  }

  try {
    const response = await authApi.loginWith2FA({
      username: challenge.username,
      password: challenge.password,
      otp: code,
    });
    return { status: 'authenticated', user: response.data };
  } catch (error) {
    return {
      status: 'failed',
      error: getApiErrorMessage(error, 'That code was not accepted.'),
    };
  }
};

/**
 * Ends the session. A server call in both modes, since the session itself lives
 * server side as a revocable token or an httpOnly refresh cookie.
 */
export const signOut = async (): Promise<void> => {
  const identity = getIdentityClient();
  if (identity !== null) {
    await identity.logout();
    return;
  }
  await authApi.logout();
};

/**
 * Spends the refresh cookie for an access token at startup, identity mode only.
 * Resolves false rather than throwing, since arriving signed out is normal.
 */
export const restoreSession = async (): Promise<boolean> => {
  const identity = getIdentityClient();
  if (identity === null) return false;
  try {
    await identity.initialize();
    return identity.getAccessToken() !== null;
  } catch {
    return false;
  }
};

/**
 * Turns a thrown identity error into a sentence for a form, replacing the two
 * deliberately vague enumeration-resistant messages with a concrete next step.
 */
export const describeIdentityFailure = (error: unknown): string => {
  switch (getAuthErrorCode(error)) {
    case 'INVALID_CREDENTIALS':
      return 'Incorrect email or password.';
    case 'EMAIL_NOT_VERIFIED':
      return 'Verify your email address before signing in.';
    default:
      return describeAuthError(error, 'Sign in failed. Please try again.');
  }
};

/**
 * Requests a verification email. Both modes answer identically whether or not
 * the address has an account.
 */
export const requestVerificationEmail = async (
  email: string
): Promise<{ ok: boolean; message: string }> => {
  const identity = getIdentityClient();
  if (identity !== null) {
    const outcome = await identity.requestEmailVerification({ email });
    return outcome.ok
      ? {
          ok: true,
          message: outcome.detail ?? 'Verification email sent.',
        }
      : { ok: false, message: outcome.message };
  }
  await apiClient.post('/auth/verify-email', { email });
  return { ok: true, message: 'Verification email sent.' };
};

/**
 * Requests a password reset email. Follows the auth mode because the service
 * that sends the mail also builds and confirms the link it carries; splitting
 * the two halves across mechanisms yields a link that always fails.
 */
export const requestPasswordReset = async (
  email: string
): Promise<{ ok: boolean; message: string }> => {
  const identity = getIdentityClient();
  if (identity !== null) {
    const outcome = await identity.requestPasswordReset({ email });
    return outcome.ok
      ? {
          ok: true,
          message:
            outcome.detail ??
            'If an account with that email exists, a password reset link has been sent.',
        }
      : { ok: false, message: outcome.message };
  }
  await authApi.resetPassword({ email });
  return {
    ok: true,
    message:
      'If an account with that email exists, a password reset link has been sent.',
  };
};
