// The shared API transport, adapted to the response shape this application
// already reads.
//
// The transport is `@webbpulse/api-client`, which replaced a hand-rolled
// equivalent that used to live in this file: an axios instance with a request
// interceptor that attached the bearer token, a response interceptor that
// stored a rotated token from the `x-new-access-token` header, a
// `paramsSerializer` that repeated array keys, and three `localStorage`
// helpers.
//
// This file now builds one of two clients, selected by `./authMode`.
//
// In `bearer` mode, which is what every environment still runs, it is exactly
// what it was: the token comes from `localStorage` through `./tokenStore` and
// goes out as an `Authorization` header, and a rotated token arriving in
// `x-new-access-token` is written back. `@webbpulse/auth` 0.4.0 removed
// `TokenStore` outright, which is why that store is local again rather than
// imported.
//
// In `identity` mode the client is handed an `AuthClient` as `auth` instead.
// That one object holds the access token in memory, refreshes it from an
// httpOnly cookie, collapses concurrent refreshes into one, and replays a
// request that came back 401. `./tokenStore` is then unreachable: the three
// helpers below become a read-through and two no-ops, because writing an access
// token anywhere a script can read it back is the one thing section 7.1 of the
// identity standard forbids.
//
// What did NOT change is the contract this file exports. Ninety modules under
// `src/api/`, `src/hooks/` and `src/pages/` read `response.data` off an axios
// style response and catch a rejected promise on a non 2xx, and the test suite
// mocks this module with objects of the same shape. So `apiClient` below keeps
// the `{ data }` envelope and the `{ params }` / `{ headers }` request options,
// and the adapter that maps between the two is the small block at the bottom.
// Rewriting 257 call sites to unwrap a different envelope would be a much
// larger change with no behavioural gain, and the brief for this migration is
// to adapt at the service boundary instead.
//
// `createEnvelopeClient` from the shared package is deliberately not used here.
// It converts a rejection into `{ data: T | null, error }`, which is what
// Portfolio's call sites expect. CarModPicker's are the opposite: they `await`
// into a `try` block, catch the rejection, and read a `data` the types say is
// never null. Wrapping the client in the envelope would make every one of those
// call sites silently succeed with `data === null` on a failed request. So this
// file keeps the throwing client and only reshapes the success value.
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
 * Token storage key. Unchanged from the hand-rolled version: changing it would
 * sign every existing user out on the deploy that adopted this package.
 */
const TOKEN_STORAGE_KEY = 'access_token';

/**
 * Probes `localStorage` with a real write and falls back to an in-memory store.
 * Safari in private mode exposes a `localStorage` whose `setItem` throws, which
 * the direct calls this replaced did not survive.
 */
const tokenStore = new TokenStore(TOKEN_STORAGE_KEY);

/**
 * Get the token.
 *
 * In identity mode there is nothing in `localStorage` to get, and the access
 * token lives in `AuthClient`'s closure. Reading it through here rather than
 * returning null keeps the one caller that genuinely needs the raw string,
 * `ExtensionAuth`, working in both modes off a single call.
 */
export const getStoredToken = (): string | null =>
  AUTH_MODE === 'identity'
    ? (getIdentityClient()?.getAccessToken() ?? null)
    : tokenStore.get();

/**
 * Store the token.
 *
 * A no-op in identity mode. Section 7.1 of the identity standard puts the
 * access token in memory and nowhere a script can read it back after a reload,
 * so writing it to `localStorage` would defeat the control the whole mode
 * exists for. `AuthClient` owns the token; nothing outside it may put one back.
 */
export const setStoredToken = (token: string): void => {
  if (AUTH_MODE === 'identity') return;
  tokenStore.set(token);
};

/**
 * Forget the token.
 *
 * In identity mode the session is the refresh cookie rather than anything
 * local, and only the server can revoke it, so the caller wants
 * `AuthClient.logout()` and this becomes a no-op. It is left callable so the
 * two error paths in `AuthContext` do not need a mode branch of their own.
 */
export const removeStoredToken = (): void => {
  if (AUTH_MODE === 'identity') return;
  tokenStore.clear();
};

/**
 * The identity token provider, or undefined in bearer mode.
 *
 * Passing `auth` is what turns on the shared client's retry-once-on-401
 * pipeline: it reads the access token before each request, and on a 401 calls
 * `refresh()` once, waits on the single in-flight refresh if one is already
 * running, and replays the request. That is the entire mechanism, and it
 * replaces `getAuthToken` plus `onTokenRefresh` rather than joining them.
 */
const identityAuth = AUTH_MODE === 'identity' ? getIdentityClient() : null;

const sharedClient = createApiClient({
  baseUrl: appConfig.apiBaseUrl,
  // Send cookies on cross-subdomain calls to the API host. Staging sits behind
  // the access gate, whose CloudFront signed cookies are set on the staging
  // apex, so a request from www.staging to api.staging only carries them when
  // the browser is told to include credentials. Both backends run CORS with
  // allow_credentials and an explicit origin list, so this is safe in every
  // environment; auth itself still rides on the Bearer token below.
  //
  // This is the shared client's default, stated explicitly because it is load
  // bearing here rather than incidental. In identity mode it is load bearing
  // twice over: the refresh cookie is httpOnly and only travels on a
  // credentialed request.
  credentials: 'include',
  timeoutMs: 30000,
  // Exactly one of these two branches is live in a given bundle. In identity
  // mode `auth` supplies the token and owns refreshing it; in bearer mode
  // `getAuthToken` reads `localStorage` and `onTokenRefresh` writes back the
  // rotated token the API sends in `x-new-access-token`, for example after a
  // username change. Handing the client both would let a stale stored token
  // shadow the in-memory one.
  ...(identityAuth !== null
    ? { auth: identityAuth }
    : { getAuthToken: getStoredToken, onTokenRefresh: setStoredToken }),
});

/**
 * The response shape this application's call sites destructure.
 *
 * Only `data` is exposed. The shared client resolves with `status` and
 * `headers` alongside it, and those pass through untouched at runtime, but no
 * call site in this application reads either: the status that matters is on the
 * thrown `ApiError`, and the one response header that mattered
 * (`x-new-access-token`) is consumed by the client itself. Narrowing the type
 * to what is actually used keeps a caller from taking a dependency on the
 * transport, and lets a test stub a response with the one field it cares about.
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
 * Maps axios `params` onto the shared client's `query`.
 *
 * `URLSearchParams` is accepted because a few call sites build one directly.
 * Array values repeat the key (`ids=1&ids=2`) in the shared client, which is
 * what the backend's `ids` and `category_ids` parameters require and what the
 * removed `paramsSerializer` used to do by hand.
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
 * Translates an axios style config into shared client `RequestOptions`.
 *
 * The Content-Type handling is the part that matters. Axios inferred a body
 * encoding from the header it was given; the shared client infers it from the
 * body's type and deliberately leaves `FormData` alone so the browser can set
 * its own multipart boundary. So:
 *
 *   - `multipart/form-data` is dropped. Forwarding it would send a boundary-less
 *     header and the backend would fail to parse the upload. The body is
 *     already a `FormData`, which the shared client passes through untouched.
 *   - `application/x-www-form-urlencoded` is honoured by encoding a plain
 *     object body into `URLSearchParams`, which axios used to do implicitly.
 *     The login endpoint depends on this.
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
      // Dropped on purpose: the browser must supply the boundary.
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
          // Only primitives are encodable. A nested object has no
          // form-urlencoded representation and would be appended as the
          // literal string "[object Object]", which the backend would accept
          // and then fail to parse. Skipping it surfaces the missing field at
          // the API instead of sending a corrupt value.
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
      // `URLSearchParams` already carries this content type, so the header is
      // not forwarded either way.
      continue;
    }
    headers[key] = value;
  }
  if (Object.keys(headers).length > 0) options.headers = headers;

  return { options, body: encodedBody };
};

/**
 * The application-facing client.
 *
 * Every method resolves to `{ data, status, headers }` and rejects with the
 * shared `ApiError` on a non 2xx, which is the same "reject on failure"
 * contract the axios instance had. Error consumers read `error.status` and
 * `error.body` rather than `error.response`; `isApiErrorWithStatus` below is
 * the helper for the handful of sites that need the status.
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

/**
 * True when the error came back from the API carrying an HTTP status.
 *
 * Replaces `axios.isAxiosError(error)` plus a `error.response?.status` reach.
 */
export const isApiErrorWithStatus = (error: unknown): error is ApiError =>
  error instanceof ApiError;

export default apiClient;
