/**
 * The TOTP and recovery code operations in identity mode.
 *
 * ## Why this is separate from the legacy 2FA calls
 *
 * `./auth` speaks CarModPicker's own routes: `POST /auth/2fa/setup` answers a
 * secret and a QR payload, and enable and disable take a password alongside the
 * code. The identity service takes `{ "code" }` and nothing else, because the
 * session itself is the proof of who is asking and a password field on a form
 * the user is already signed into buys nothing.
 *
 * The other real difference is **recovery codes**. Activating TOTP on the
 * identity service issues ten of them, in plaintext, exactly once. The legacy
 * flow has none, which is why a cutover prompts every already-enrolled user to
 * generate a set: `identityAvailability().recoveryCodes` is the flag the panel
 * reads for that.
 *
 * Every function returns a discriminated result rather than throwing, matching
 * `./identityAuth` and `./identityPasskeys`, so a panel renders a refusal the
 * same way whichever operation produced it.
 */
import { getIdentityClient } from './identityClient';

/** What one TOTP operation produced. */
export type TotpResult<T> =
  | { status: 'ok'; value: T }
  | { status: 'failed'; error: string };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Two factor authentication is managed elsewhere in this deployment.';

/** What an enrolment start produced, for rendering a QR code and a seed. */
export interface TotpEnrolment {
  /** The base32 seed, for a user who cannot scan. Shown exactly once. */
  secret: string;
  /** The `otpauth://totp/...` URI to render as a QR code. */
  provisioningUri: string;
}

/**
 * Begins enrolment, producing the secret and the provisioning URI.
 *
 * Nothing is switched on yet: the factor is pending until a code from the
 * authenticator proves the seed was actually stored, which is `activateTotp`.
 */
export const enrolTotp = async (): Promise<TotpResult<TotpEnrolment>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.enrolTotp();
    return outcome.ok
      ? {
          status: 'ok',
          value: {
            secret: outcome.secret,
            provisioningUri: outcome.provisioningUri,
          },
        }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not start two factor setup.',
    };
  }
};

/**
 * Turns the pending factor on, and returns the recovery codes.
 *
 * The codes come back in plaintext exactly once. The server stores only hashes
 * and has no route that reads them back, so a panel that does not show them
 * here has lost them: the only way to see a set again is to replace it with
 * `regenerateRecoveryCodes`.
 */
export const activateTotp = async (
  code: string
): Promise<TotpResult<string[]>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.activateTotp({ code: code.trim() });
    return outcome.ok
      ? { status: 'ok', value: outcome.recoveryCodes }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not turn on two factor authentication.',
    };
  }
};

/**
 * Turns the factor off.
 *
 * Takes a code and no password, unlike the legacy route. A recovery code is
 * accepted here too, which is what lets a user who lost the authenticator turn
 * it off rather than being locked out of their own settings.
 */
export const disableTotp = async (
  code: string
): Promise<TotpResult<null>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.disableTotp({ code: code.trim() });
    return outcome.ok
      ? { status: 'ok', value: null }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not turn off two factor authentication.',
    };
  }
};

/**
 * Replaces the recovery code set, invalidating the previous one.
 *
 * The new codes are shown exactly once, on the same terms as activation's. This
 * is also the route an already-enrolled user reaches after a cutover, since the
 * legacy flow issued no codes at all and their account has none until they ask
 * for a set.
 */
export const regenerateRecoveryCodes = async (
  code: string
): Promise<TotpResult<string[]>> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.regenerateRecoveryCodes({
      code: code.trim(),
    });
    return outcome.ok
      ? { status: 'ok', value: outcome.recoveryCodes }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not generate new recovery codes.',
    };
  }
};
