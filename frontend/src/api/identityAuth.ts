/**
 * The sign in and sign out operations, in the one shape both modes answer.
 *
 * `./auth` is the legacy surface and stays exactly as it is: it speaks
 * `/auth/token`, stores a bearer token, and is what runs in every environment
 * today. This module sits above both mechanisms and hands the pages a result
 * they can render without knowing which one produced it.
 *
 * ## Why a union rather than a thrown error
 *
 * The identity standard makes an MFA challenge a *successful* outcome of the
 * first leg that simply carries no access token. The legacy flow models the
 * same thing as `requires_2fa: true` in a 200 body. Neither is an error, and
 * the login page has three things to render rather than two, so the return type
 * says so. What is left to throw is a network failure, which no form can render
 * a field level message for anyway.
 *
 * ## Why the two second legs are not the same call
 *
 * Legacy `/auth/token/2fa` re-sends the username and password alongside the
 * code, because the server holds no state between the legs. Identity issues a
 * short lived ticket in the first leg and takes `{ ticket, code }` in the
 * second, and deliberately never sees the password twice. `LoginChallenge`
 * below carries whichever of the two the mode produced, so the page holds one
 * opaque value and hands it back.
 */
import { describeAuthError, getAuthErrorCode } from '@webbpulse/auth';
import { AUTH_MODE } from './authMode';
import { getIdentityClient } from './identityClient';
import { authApi } from './auth';
import { apiClient } from './client';
import type { UserRead } from '../types/Api';
import { getApiErrorMessage } from '../utils/apiError';

/**
 * What the second leg of a sign in needs, whichever mechanism ran the first.
 *
 * In identity mode the ticket is the server's, and the password is gone. In
 * bearer mode the server keeps no state between the legs, so the credentials
 * are the ticket. The page treats it as opaque either way, which is what keeps
 * the login form free of a mode branch.
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
 * True when the code field should also accept a recovery code.
 *
 * Only the identity service issues recovery codes; the legacy TOTP flow has
 * none. This is what widens the input from six digits to free text, and it is a
 * function rather than a constant so a test can drive both.
 */
export const acceptsRecoveryCodes = (): boolean => AUTH_MODE === 'identity';

/**
 * Runs the first leg of a sign in.
 *
 * The identity branch never touches `localStorage`: `AuthClient` settles the
 * access token into its own closure and the refresh cookie is set by the
 * server. It also returns no user, because this application reads roughly
 * twenty `UserRead` fields that no token claim carries, so the caller follows a
 * success with `checkAuthStatus()` in both modes.
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
      // `user` is whatever `loadUser` produced, and no `loadUser` is
      // configured, so it is null by construction. The caller fetches the
      // user; see `identityClient`.
      return { status: 'authenticated', user: null };
    } catch (error) {
      return { status: 'failed', error: describeIdentityFailure(error) };
    }
  }

  try {
    const response = await authApi.login({ username, password });
    // Already `UserRead | LoginResponse`: `authApi.login` returns the 2FA
    // challenge body untouched and unwraps `data.user` otherwise.
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
 *
 * The server tells the two apart by length and shape, so there is one field and
 * one call rather than a radio button the user has to get right.
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
        // A second challenge from the second leg means the ticket was spent
        // and reissued, which the server does not do. Treated as a refusal
        // rather than looping.
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
 * Ends the session.
 *
 * Both branches are a server call rather than a local clear, because in both
 * mechanisms the thing that actually ends the session lives on the server: the
 * legacy route revokes, and the identity route clears the httpOnly refresh
 * cookie the page cannot touch.
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
 * Restores a session at startup, if the browser still holds one.
 *
 * Identity only. `initialize()` spends the refresh cookie for a fresh access
 * token, and a failure means "no session", not "something broke": arriving
 * signed out is the normal state for most page loads. So this resolves to a
 * boolean rather than throwing, and the caller treats false as anonymous.
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
 * Turns a thrown identity error into a sentence for a form.
 *
 * `describeAuthError` already prefers the server's own message, which is
 * written to be shown. The two codes named here are the ones whose server
 * wording is deliberately vague for enumeration resistance and which a user
 * needs a concrete next step for.
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
 * Requests a verification email for the signed in user.
 *
 * The legacy route takes the address in the body; the identity route takes it
 * too, and answers identically whether or not the address has an account.
 * Both are a fire and forget from this application's point of view.
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
 * Requests a password reset email.
 *
 * The mailed link is the reason this has to follow the mode rather than stay on
 * the legacy route. Whichever service sends the mail also builds the URL in it
 * and is the only one that can confirm the token it carries: the legacy mail
 * points at `/auth/reset-password/confirm` and the identity mail points at
 * `RESET_PASSWORD_PATH`, which `ResetPassword` serves. Sending the request to
 * one service and landing the user on the other's confirm page is a link that
 * always fails, so the two halves are kept on the same mechanism here.
 *
 * Both answer identically whether or not the address has an account, which is
 * deliberate on both sides and is why the caller gets no way to tell.
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
