/**
 * Reading the API's error envelope.
 *
 * Every error response from the backend is the shared WebbPulse envelope:
 *
 *   { success: false, status: 404, message: "...", request_id: "...",
 *     error_code?: "NOT_FOUND", details?: ... }
 *
 * There used to be three shapes to cope with — an unmatched route returned
 * FastAPI's raw `{ detail: "Not Found" }`, handled errors returned
 * `{ success, message, error_code }`, and a 422 added `details` — which is why
 * call sites read `data.message || data.detail` in a fallback chain. The
 * backend now renders one shape everywhere, so `message` is the only field to
 * read and the `.detail` fallbacks are gone.
 *
 * This envelope is CarModPicker's own and stays local. `formatApiErrorMessage`
 * in `@webbpulse/api-client` reads FastAPI's `detail` or a bare `message`,
 * neither of which carries `error_code` or the structured `details` this
 * application branches on, so the shared formatter would lose information here.
 */
import { ApiError } from '@webbpulse/api-client';

/** The error body every backend response carries on a non-2xx status. */
export interface ApiErrorEnvelope {
  success: false;
  status: number;
  message: string;
  request_id: string;
  /** Present on every handled error; a route may set its own, e.g. PART_ALREADY_EXISTS. */
  error_code?: string;
  /**
   * A list of per-field entries on a 422, or a route-specific object on other
   * statuses. Echoed from the server verbatim, so never assume a shape without
   * checking the status or the error code first.
   */
  details?: ValidationDetail[] | Record<string, unknown>;
}

/** One offending field in a 422 body. */
export interface ValidationDetail {
  field: string;
  message: string;
  type: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

/**
 * The error body from an unknown thrown value, or null when there isn't one.
 *
 * Anything can be thrown — a network failure has no response at all — so this
 * narrows rather than asserts, and every consumer supplies its own fallback
 * message for the cases it returns null on.
 *
 * Two carriers are accepted. `ApiError` from `@webbpulse/api-client` holds the
 * parsed body on `.body`, and that is what the transport throws now. The older
 * `response.data` shape is still read because a rejection that carries it with
 * a string `message` is the same envelope, and some call sites construct one.
 */
export const getApiErrorEnvelope = (err: unknown): ApiErrorEnvelope | null => {
  if (!isRecord(err)) return null;
  const body = err instanceof ApiError ? err.body : readLegacyBody(err);
  if (!isRecord(body)) return null;
  if (typeof body['message'] !== 'string') return null;
  return body as unknown as ApiErrorEnvelope;
};

/** The `response.data` an axios style rejection used to carry. */
const readLegacyBody = (err: Record<string, unknown>): unknown => {
  const response = err['response'];
  return isRecord(response) ? response['data'] : undefined;
};

/**
 * The message to show the user for a failed request.
 *
 * Falls back to `fallback` when the response carried no envelope, which covers
 * a network error, a timeout, and anything a proxy returned instead of the API.
 */
export const getApiErrorMessage = (err: unknown, fallback: string): string => {
  const envelope = getApiErrorEnvelope(err);
  if (envelope?.message) return envelope.message;
  // A plain Error that never reached the API (a thrown guard, an aborted
  // request) still says more than the generic fallback does. Anything that
  // reached the API has already been handled above, or carried a body this
  // helper could not read, and its raw message is not user facing.
  if (err instanceof ApiError) return fallback;
  if (isRecord(err) && 'response' in err) return fallback;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
};

/** The machine readable code, for branching on a specific failure. */
export const getApiErrorCode = (err: unknown): string | undefined =>
  getApiErrorEnvelope(err)?.error_code;

/**
 * The per-field entries of a 422, or an empty list for any other error.
 *
 * Guarded on the shape rather than the status, because `details` on a
 * non-validation error is a route-specific object rather than this list.
 */
export const getApiValidationDetails = (err: unknown): ValidationDetail[] => {
  const details = getApiErrorEnvelope(err)?.details;
  if (!Array.isArray(details)) return [];
  return details.filter(
    (entry): entry is ValidationDetail =>
      isRecord(entry) &&
      typeof entry.field === 'string' &&
      typeof entry.message === 'string'
  );
};

/**
 * A route-specific `details` object, for the handful of errors that attach one
 * (the duplicate-part conflict carries `existing_part_id`, for instance).
 */
export const getApiErrorDetails = (
  err: unknown
): Record<string, unknown> | null => {
  const details = getApiErrorEnvelope(err)?.details;
  return isRecord(details) && !Array.isArray(details) ? details : null;
};
