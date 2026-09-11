/**
 * Narrowing an unknown thrown value onto `@webbpulse/api-client`.
 *
 * The envelope reading itself is no longer here. `@webbpulse/api-client` 0.3.0
 * added `WebbPulseErrorBody`, `isWebbPulseErrorBody` and `getWebbPulseError`,
 * which read `{ success, status, message, request_id, error_code, details }`
 * as a first class shape, so the local type, type guard, message chain, code
 * accessor and details accessors that used to fill this file are gone. What is
 * left is the one thing the package deliberately does not do: accept an
 * `unknown`.
 *
 * `getWebbPulseError` takes an `ApiError`, because a caller that has narrowed
 * to one should not have to pass `unknown` and get back a half-populated
 * result. Every call site in this application catches an `unknown` instead, and
 * roughly two dozen of them want a message with a fallback. Rather than repeat
 * `error instanceof ApiError ? ... : fallback` at each, the narrowing lives
 * here once and the rest of the application keeps the signatures it had.
 */
import {
  ApiError,
  getWebbPulseError,
  isWebbPulseErrorBody,
} from '@webbpulse/api-client';

/**
 * The message to show the user for a failed request.
 *
 * The envelope's `message` when the body is one, and `fallback` otherwise.
 *
 * Both guards are on the body rather than on the message `getWebbPulseError`
 * returns, and that is the whole subtlety here. The package synthesises
 * "Request failed with status 500." from the status line whenever the body
 * yields nothing readable, which is a true statement and a useless one to show
 * a user: the caller passed "Failed to change password" precisely because it
 * knows what the user was doing and the transport does not. Checking the
 * accessor's output could not tell that synthesised line from a real message,
 * so the body is what gets inspected, and a body that is not an envelope or
 * whose `message` is blank takes the caller's fallback. That is what this
 * application did before the envelope reading moved into the package.
 *
 * A value that never reached the API at all is different again. A plain `Error`
 * (a thrown guard, an aborted request) carries a message written for this
 * situation, so it is preferred over the fallback.
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
 * A route-specific `details` object, for the handful of errors that attach one
 * (the duplicate-part conflict carries `existing_part_id`, for instance).
 *
 * The package types `details` as `unknown[] | Record<string, unknown> |
 * undefined`, so the array case is excluded here rather than asserted away: a
 * 422's `details` is the per-field list, which is a different shape and not
 * what this accessor is for.
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
