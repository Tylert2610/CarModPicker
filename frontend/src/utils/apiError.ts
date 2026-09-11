/**
 * Narrows an unknown thrown value onto `@webbpulse/api-client`'s error
 * envelope, which the package itself reads only from an already narrowed
 * `ApiError`. Every call site here catches an `unknown`.
 */
import {
  ApiError,
  getWebbPulseError,
  isWebbPulseErrorBody,
} from '@webbpulse/api-client';

/**
 * The message to show for a failed request. Guards on the body rather than the
 * accessor's output, so the package's synthesised status line never displaces
 * the caller's fallback, which knows what the user was doing.
 */
export const getApiErrorMessage = (err: unknown, fallback: string): string => {
  if (err instanceof ApiError) {
    if (!isWebbPulseErrorBody(err.body)) return fallback;
    if (err.body.message.trim() === '') return fallback;
    return getWebbPulseError(err).message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
};

/** The machine readable code, for branching on a specific failure. */
export const getApiErrorCode = (err: unknown): string | undefined =>
  err instanceof ApiError ? getWebbPulseError(err).errorCode : undefined;

/**
 * A route-specific `details` object, for the errors that attach one. Excludes
 * the array case, which is a 422's per-field list and a different shape.
 */
export const getApiErrorDetails = (
  err: unknown
): Record<string, unknown> | null => {
  if (!(err instanceof ApiError)) return null;
  const { details } = getWebbPulseError(err);
  return typeof details === 'object' &&
    details !== null &&
    !Array.isArray(details)
    ? details
    : null;
};
