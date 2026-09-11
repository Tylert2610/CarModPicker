/**
 * Passkey operations in identity mode, giving the panels one shape to render
 * above `AuthClient`'s outcome unions. Bearer mode keeps its own
 * `@simplewebauthn/browser` path in `./auth`.
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
 * Turns a thrown package error into an outcome. A dismissed browser sheet is
 * its own status, so the panel stops rather than showing an error.
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
 * Enrols a new passkey, running both ceremony legs inside `AuthClient` so the
 * single-use options are never held across a user interaction.
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
 * Removes one passkey. Deleting the last credential on an account with no other
 * way in is refused, carrying the server's own explanation.
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
 * Signs in with a passkey and no password. `mediation` is passed through so the
 * page can request `conditional` autofill. An `mfa-required` outcome is ordinary
 * for an account with TOTP on, and its ticket goes to the usual `completeMfa`.
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
