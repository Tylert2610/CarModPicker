/**
 * The sign in and sign out operations, in the shape the pages render.
 *
 * There used to be two mechanisms behind this module. The legacy one spoke
 * CarModPicker's own `/api/auth` routes and kept a bearer token in
 * `localStorage`; row 13 of `docs/identity-adoption.md` deleted all 24 of those
 * routes, so the only mechanism left is the unified identity standard that
 * `@webbpulse/auth` implements as `AuthClient`. This module is the seam between
 * that package's outcome types and what a form can actually render.
 *
 * ## Why a union rather than a thrown error
 *
 * The identity standard makes an MFA challenge a *successful* outcome of the
 * first leg that simply carries no access token. It is not an error, and the
 * login page has three things to render rather than two, so the return type
 * says so. What is left to throw is a network failure, which no form can render
 * a field level message for anyway.
 *
 * ## Why the second leg takes a ticket rather than the password again
 *
 * The identity service issues a short lived ticket in the first leg and takes
 * `{ ticket, code }` in the second, so it deliberately never sees the password
 * twice. `LoginChallenge` below carries that ticket, and the page holds it as an
 * opaque value and hands it back.
 *
 * ## Why every function still handles a null client
 *
 * `getIdentityClient()` can return null, and that no longer means "this bundle
 * runs the legacy flow": it means construction failed. See the doc comment on
 * `getIdentityClient` in `./identityClient`. There is nothing to fall back to
 * any more, so each function turns the null into a refusal the caller can show,
 * rather than throwing from a module the whole bundle imports.
 */
import { describeAuthError, getAuthErrorCode } from '@webbpulse/auth';
import { getIdentityClient } from './identityClient';
import type { UserRead } from '../types/Api';

/**
 * The sentence shown when the identity client could not be built at all.
 *
 * One string rather than a per-function wording, because the cause is the same
 * every time and it is a deployment fault rather than anything the user did.
 */
const CLIENT_UNAVAILABLE = 'Sign in is unavailable in this deployment.';

/**
 * What the second leg of a sign in needs.
 *
 * A single variant, and the `kind` discriminator is kept rather than flattened
 * away: `Login` and the passkey and OAuth paths all build one of these by name,
 * and a tagged shape is what lets a second challenge type be added later
 * without every construction site becoming ambiguous.
 */
export type LoginChallenge = {
  kind: 'identity-ticket';
  ticket: string;
  factors: string[];
};

/** What a sign in attempt produced. */
export type LoginResult =
  | { status: 'authenticated'; user: UserRead | null }
  | { status: 'mfa-required'; challenge: LoginChallenge }
  | { status: 'failed'; error: string };

/**
 * True when the code field should also accept a recovery code.
 *
 * The identity service issues recovery codes, so this is now constant. It stays
 * a function rather than becoming an inlined `true` at the call site because
 * what the login page is asking is "does the checking service accept these",
 * which is a property of the auth mechanism and belongs next to it: if a
 * deployment ever answers differently, this is the one place that changes.
 */
export const acceptsRecoveryCodes = (): boolean => true;

/**
 * Runs the first leg of a sign in.
 *
 * This never touches `localStorage`: `AuthClient` settles the access token into
 * its own closure and the refresh cookie is set by the server. It also returns
 * no user, because this application reads roughly twenty `UserRead` fields that
 * no token claim carries, so the caller follows a success with
 * `checkAuthStatus()`.
 */
export const signIn = async (
  username: string,
  password: string
): Promise<LoginResult> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { status: 'failed', error: CLIENT_UNAVAILABLE };
  }
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
};

/**
 * Runs the second leg with a TOTP code or a recovery code.
 *
 * The server tells the two apart by length and shape, so there is one field and
 * one call rather than a radio button the user has to get right.
 */
export const completeMfa = async (
  challenge: LoginChallenge,
  code: string
): Promise<LoginResult> => {
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
};

/**
 * Ends the session.
 *
 * A server call rather than a local clear, because the thing that actually ends
 * the session lives on the server: the identity route clears the httpOnly
 * refresh cookie the page cannot touch. A null client means there is no session
 * to end either, so this resolves rather than refusing: the caller's next step
 * is to drop its own user state, which is right in both cases.
 */
export const signOut = async (): Promise<void> => {
  const identity = getIdentityClient();
  if (identity === null) return;
  await identity.logout();
};

/**
 * Restores a session at startup, if the browser still holds one.
 *
 * `initialize()` spends the refresh cookie for a fresh access token, and a
 * failure means "no session", not "something broke": arriving signed out is the
 * normal state for most page loads. So this resolves to a boolean rather than
 * throwing, and the caller treats false as anonymous.
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
 * The identity route takes the address in the body and answers identically
 * whether or not the address has an account, which is deliberate and is why the
 * caller gets no way to tell.
 */
export const requestVerificationEmail = async (
  email: string
): Promise<{ ok: boolean; message: string }> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { ok: false, message: CLIENT_UNAVAILABLE };
  }
  const outcome = await identity.requestEmailVerification({ email });
  return outcome.ok
    ? { ok: true, message: outcome.detail ?? 'Verification email sent.' }
    : { ok: false, message: outcome.message };
};

/**
 * Requests a password reset email.
 *
 * The mailed link is why this belongs next to the rest of the mechanism rather
 * than anywhere else: the service that sends the mail also builds the URL in it
 * and is the only one that can confirm the token it carries. The identity mail
 * points at `RESET_PASSWORD_PATH`, which `ResetPassword` serves.
 *
 * The answer is identical whether or not the address has an account, which is
 * deliberate and is why the caller gets no way to tell.
 */
export const requestPasswordReset = async (
  email: string
): Promise<{ ok: boolean; message: string }> => {
  const identity = getIdentityClient();
  if (identity === null) {
    return { ok: false, message: CLIENT_UNAVAILABLE };
  }
  const outcome = await identity.requestPasswordReset({ email });
  return outcome.ok
    ? {
        ok: true,
        message:
          outcome.detail ??
          'If an account with that email exists, a password reset link has been sent.',
      }
    : { ok: false, message: outcome.message };
};
