/**
 * Shared HTTP client for the CarModPicker API. Resolves the access token from
 * whichever auth mode is active, so callers never branch on mode themselves.
 */

import {
  ApiError,
  createApiClient,
  type QueryParams,
  type RequestOptions,
} from '@webbpulse/api-client';
import { TokenStore } from './tokenStore';
import { AUTH_MODE } from './authMode';
import { getIdentityClient } from './identityClient';
import { appConfig } from '../config/app';

/**
 * Key the bearer token is stored under. Changing it signs every existing user
 * out on the next deploy.
 */
const TOKEN_STORAGE_KEY = 'access_token';

/**
 * Token store that probes `localStorage` and falls back to memory, so Safari
 * private mode (whose `setItem` throws) still works.
 */
const tokenStore = new TokenStore(TOKEN_STORAGE_KEY);

/**
 * Returns the access token, from `AuthClient` in identity mode and from
 * `localStorage` in bearer mode, so callers need no mode branch.
 */
export const getStoredToken = (): string | null =>
  AUTH_MODE === 'identity'
    ? (getIdentityClient()?.getAccessToken() ?? null)
    : tokenStore.get();

/**
 * Stores the access token in bearer mode. A no-op in identity mode, where the
 * token must stay in memory and only `AuthClient` may set it.
 */
export const setStoredToken = (token: string): void => {
  if (AUTH_MODE === 'identity') return;
  tokenStore.set(token);
};

/**
 * Clears the stored access token in bearer mode. A no-op in identity mode,
 * where only the server can revoke the refresh cookie.
 */
export const removeStoredToken = (): void => {
  if (AUTH_MODE === 'identity') return;
  tokenStore.clear();
};

/**
 * Identity token provider, or null in bearer mode. Supplying it enables the
 * shared client's refresh-once-on-401 retry.
 */
const identityAuth = AUTH_MODE === 'identity' ? getIdentityClient() : null;

const sharedClient = createApiClient({
  baseUrl: appConfig.apiBaseUrl,
  credentials: 'include',
  timeoutMs: 30000,
  ...(identityAuth !== null
    ? { auth: identityAuth }
    : { getAuthToken: getStoredToken, onTokenRefresh: setStoredToken }),
});

/**
 * Response shape call sites destructure. Only `data` is exposed so callers do
 * not depend on the transport; status arrives on the thrown `ApiError`.
 */
export interface ApiClientResponse<T> {
  data: T;
}

/** The axios-shaped request options this application's call sites pass. */
export interface ApiRequestConfig {
  params?: QueryParams | URLSearchParams | undefined;
  headers?: Record<string, string> | undefined;
  signal?: AbortSignal | undefined;
}

/**
 * Maps axios-style `params` onto the shared client's `query`, accepting a
 * `URLSearchParams` and repeating keys for array values as the backend needs.
 */
const toQuery = (
  params: ApiRequestConfig['params']
): QueryParams | undefined => {
  if (params === undefined) return undefined;
  if (params instanceof URLSearchParams) {
    const query: QueryParams = {};
    for (const [key, value] of params.entries()) {
      const existing = query[key];
      if (existing === undefined) {
        query[key] = value;
      } else if (Array.isArray(existing)) {
        existing.push(value);
      } else {
        query[key] = [existing as string, value];
      }
    }
    return query;
  }
  return params;
};

/**
 * Translates an axios-style config into shared client `RequestOptions`. Drops
 * `multipart/form-data` so the browser sets its own boundary, and encodes a
 * form-urlencoded body into `URLSearchParams`.
 */
const toRequestOptions = (
  config: ApiRequestConfig | undefined,
  body?: unknown
): { options: RequestOptions; body: unknown } => {
  const options: RequestOptions = {};
  const query = toQuery(config?.params);
  if (query !== undefined) options.query = query;
  if (config?.signal !== undefined) options.signal = config.signal;

  let encodedBody = body;
  const headers: Record<string, string> = {};
  for (const [key, value] of Object.entries(config?.headers ?? {})) {
    const contentType =
      key.toLowerCase() === 'content-type' ? value.toLowerCase() : undefined;
    if (contentType?.includes('multipart/form-data') === true) {
      continue;
    }
    if (contentType?.includes('application/x-www-form-urlencoded') === true) {
      if (
        typeof encodedBody === 'object' &&
        encodedBody !== null &&
        !(encodedBody instanceof URLSearchParams) &&
        !(encodedBody instanceof FormData)
      ) {
        const search = new URLSearchParams();
        for (const [field, fieldValue] of Object.entries(
          encodedBody as Record<string, unknown>
        )) {
          if (
            typeof fieldValue === 'string' ||
            typeof fieldValue === 'number' ||
            typeof fieldValue === 'boolean'
          ) {
            search.append(field, String(fieldValue));
          }
        }
        encodedBody = search;
      }
      continue;
    }
    headers[key] = value;
  }
  if (Object.keys(headers).length > 0) options.headers = headers;

  return { options, body: encodedBody };
};

/**
 * Application-facing client. Each method resolves to `{ data }` and rejects
 * with `ApiError` on a non 2xx.
 */
export const apiClient = {
  get: <T = unknown>(
    path: string,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options } = toRequestOptions(config);
    return sharedClient.get<T>(path, options);
  },
  post: <T = unknown>(
    path: string,
    data?: unknown,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options, body } = toRequestOptions(config, data);
    return sharedClient.post<T>(path, body, options);
  },
  put: <T = unknown>(
    path: string,
    data?: unknown,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options, body } = toRequestOptions(config, data);
    return sharedClient.put<T>(path, body, options);
  },
  patch: <T = unknown>(
    path: string,
    data?: unknown,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options, body } = toRequestOptions(config, data);
    return sharedClient.patch<T>(path, body, options);
  },
  delete: <T = unknown>(
    path: string,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options } = toRequestOptions(config);
    return sharedClient.delete<T>(path, options);
  },
};

/** True when the error came back from the API carrying an HTTP status. */
export const isApiErrorWithStatus = (error: unknown): error is ApiError =>
  error instanceof ApiError;

export default apiClient;
