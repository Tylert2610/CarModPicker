/**
 * TOTP and recovery code operations in identity mode, which take a code alone
 * since the session proves who is asking. Activation issues recovery codes that
 * the legacy flow has none of. Every function returns a result, never throws.
 */
import { getIdentityClient } from './identityClient';

/** What one TOTP operation produced. */
export type TotpResult<T> =
  { status: 'ok'; value: T } | { status: 'failed'; error: string };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE =
  'Two factor authentication is managed elsewhere in this deployment.';

/** What an enrolment start produced, for rendering a QR code and a seed. */
export interface TotpEnrolment {
  /** The base32 seed, for a user who cannot scan. Shown exactly once. */
  secret: string;
  /** The `otpauth://totp/...` URI to render as a QR code. */
  provisioningUri: string;
}

/**
 * Begins enrolment, producing the secret and provisioning URI. The factor stays
 * pending until {@link activateTotp} proves the seed was stored.
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
 * Turns the pending factor on and returns the recovery codes, which arrive in
 * plaintext exactly once; the server keeps only hashes.
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
 * Turns the factor off. Accepts a recovery code as well, so a user who lost
 * their authenticator is not locked out of their own settings.
 */
export const disableTotp = async (code: string): Promise<TotpResult<null>> => {
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
 * Replaces the recovery code set, invalidating the previous one. Also how a
 * user enrolled under the legacy flow obtains their first set.
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
