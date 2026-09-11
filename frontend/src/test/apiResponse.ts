/**
 * Builders for the values `src/api/client.ts` resolves and rejects with, so a
 * test states the field under test rather than a response's worth of ceremony.
 */
import { ApiError } from '@webbpulse/api-client';
import type { ApiClientResponse } from '../api/client';

/** A successful response carrying `data`. */
export function buildResponse<T>(data: T): ApiClientResponse<T> {
  return { data };
}

/**
 * The error the client rejects with on a non 2xx.
 *
 * `body` is the backend's error envelope, which `getWebbPulseError` in
 * `@webbpulse/api-client` reads to produce a user facing message.
 */
export function buildApiError(
  status: number,
  body: unknown,
  overrides: Partial<{ statusText: string; url: string; method: string }> = {}
): ApiError {
  return new ApiError({
    status,
    statusText: overrides.statusText ?? 'Error',
    body,
    url: overrides.url ?? 'https://api.test/api/resource',
    method: overrides.method ?? 'GET',
  });
}
