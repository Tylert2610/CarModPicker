/**
 * The passkey operations in identity mode.
 *
 * Sits above `AuthClient` the way `./identityAuth` does for sign in: the pages
 * get one shape to render and do not hold the package's outcome unions, and
 * bearer mode keeps its own `@simplewebauthn/browser` path in `./auth`
 * untouched.
 *
 * ## Where the WebAuthn adapter is injected
 *
 * `AuthClient` takes a `WebAuthnAdapter`, a structural two-method surface that
 * defaults to `navigator.credentials`. It is a **constructor** option rather
 * than a per-call one, so it is supplied once in `./identityClient` through
 * `setWebAuthnAdapterForTests` rather than threaded through every function
 * here. A jsdom test run has no authenticator and cannot produce a real
 * credential, and that seam is what lets the tests drive an enrolment and a
 * sign in without a browser.
 *
 * ## The last credential rule
 *
 * Deleting a passkey is refused by the server when it is the only credential
 * left on an account that has no other way in, which the package surfaces as
 * `PasskeyLastCredential`. It is a refusal rather than an error: the user did
 * nothing wrong and there is a concrete next step, which is to set a password
 * or enrol a second key first. `deletePasskey` returns it as such so the panel
 * renders the server's sentence rather than a generic failure.
 */
import {
  isPasskeyCancellation,
  passkeysSupported,
  type Passkey,
} from '@webbpulse/auth';
import { getIdentityClient } from './identityClient';

export { passkeysSupported };
export type { Passkey };

/** What a passkey operation produced, in the one shape the panels render. */
export type PasskeyOutcome<T> =
  | { status: 'ok'; value: T }
  | { status: 'cancelled' }
  | { status: 'failed'; error: string };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Passkeys are not available in this deployment.';

/**
 * Turns a thrown package error into an outcome.
 *
 * A cancellation is its own status rather than a failure, because a user who
 * dismissed the browser's sheet did not hit an error and should not be shown
 * one: the panel simply stops.
 */
const fromError = (
  error: unknown,
  fallback: string
): { status: 'cancelled' } | { status: 'failed'; error: string } => {
  if (isPasskeyCancellation(error)) return { status: 'cancelled' };
  return {
    status: 'failed',
    error: error instanceof Error ? error.message : fallback,
  };
};

/**
 * Enrols a new passkey for the signed in user.
 *
 * Runs both legs of the ceremony inside `AuthClient`, which is deliberate: the
 * options are spent by exactly one attempt, and holding them across a user
 * interaction is how a ceremony ends up half finished with a challenge row
 * already consumed.
 */
export const enrolPasskey = async (
  name: string
): Promise<PasskeyOutcome<Passkey>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.registerPasskey(
      name.trim() === '' ? {} : { name: name.trim() }
    );
    if (outcome.ok) return { status: 'ok', value: outcome.passkey };
    if ('reason' in outcome && outcome.reason === 'cancelled') {
      return { status: 'cancelled' };
    }
    return { status: 'failed', error: outcome.message };
  } catch (error) {
    return fromError(error, 'Could not add that passkey.');
  }
};

/** The passkeys on the signed in account, newest enrolment last. */
export const listPasskeys = async (): Promise<PasskeyOutcome<Passkey[]>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.listPasskeys();
    return outcome.ok
      ? { status: 'ok', value: outcome.passkeys }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return fromError(error, 'Could not load your passkeys.');
  }
};

/** Renames one passkey. An empty name is refused by the server, not here. */
export const renamePasskey = async (
  credentialId: string,
  name: string
): Promise<PasskeyOutcome<Passkey>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.renamePasskey(credentialId, name);
    return outcome.ok
      ? { status: 'ok', value: outcome.passkey }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return fromError(error, 'Could not rename that passkey.');
  }
};

/**
 * Removes one passkey.
 *
 * A refusal carrying the last-credential rule comes back as a `failed` with the
 * server's own sentence, which explains what to do first. See the module note.
 */
export const deletePasskey = async (
  credentialId: string
): Promise<PasskeyOutcome<null>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.deletePasskey(credentialId);
    return outcome.ok
      ? { status: 'ok', value: null }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return fromError(error, 'Could not remove that passkey.');
  }
};

/** What a passwordless sign in produced. */
export type PasskeySignInResult =
  | { status: 'authenticated' }
  | { status: 'mfa-required'; ticket: string; factors: string[] }
  | { status: 'cancelled' }
  | { status: 'failed'; error: string };

/**
 * Signs in with a passkey and no password.
 *
 * `mediation` is passed through so the login page can ask for `conditional`,
 * which is what puts the account chooser inline in the username field's
 * autofill rather than in a modal sheet. A conditional request that finds no
 * credential resolves to nothing rather than erroring, which is why a
 * cancellation is a status rather than a failure here too.
 *
 * An `mfa-required` outcome is the ordinary case for an account with TOTP on:
 * the passkey proved possession and the second factor is still owed, and the
 * ticket goes to the same `completeMfa` the password flow uses.
 */
export const signInWithPasskey = async (
  input: {
    username?: string;
    mediation?: 'silent' | 'optional' | 'conditional' | 'required';
    signal?: AbortSignal;
  } = {}
): Promise<PasskeySignInResult> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.signInWithPasskey({
      ...(input.username === undefined || input.username.trim() === ''
        ? {}
        : { email: input.username.trim() }),
      ...(input.mediation === undefined ? {} : { mediation: input.mediation }),
      ...(input.signal === undefined ? {} : { signal: input.signal }),
    });
    if (outcome.ok) {
      if (outcome.kind === 'mfa-required') {
        return {
          status: 'mfa-required',
          ticket: outcome.ticket,
          factors: outcome.factors,
        };
      }
      return { status: 'authenticated' };
    }
    if ('reason' in outcome && outcome.reason === 'cancelled') {
      return { status: 'cancelled' };
    }
    return { status: 'failed', error: outcome.message };
  } catch (error) {
    const result = fromError(error, 'Passkey sign in failed.');
    return result.status === 'cancelled'
      ? { status: 'cancelled' }
      : { status: 'failed', error: result.error };
  }
};
