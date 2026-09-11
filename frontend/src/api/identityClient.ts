/**
 * Builds the `@webbpulse/auth` client, lazily and only in identity mode. Kept
 * out of `./client` so the ninety modules importing that do not construct a
 * network-capable object in bearer mode.
 */
import {
  createAuthClient,
  type AuthClient,
  type WebAuthnAdapter,
} from '@webbpulse/auth';
import { AUTH_MODE } from './authMode';
import { appConfig } from '../config/app';

/**
 * Strips the API base URL back to its origin, since `AuthClient`'s default
 * paths are already absolute and a `/api` base would send calls to
 * `/api/api/auth/...`. A relative base yields the empty string.
 */
export const identityOriginFrom = (apiBaseUrl: string): string => {
  try {
    return new URL(apiBaseUrl).origin;
  } catch {
    if (apiBaseUrl.startsWith('/')) return '';
    return apiBaseUrl;
  }
};

/**
 * Prefixes the identity origin onto an already absolute route path, for the
 * discovery gates that fetch directly instead of through `AuthClient`.
 */
export const identityUrl = (path: string): string => {
  const origin = identityOriginFrom(appConfig.apiBaseUrl);
  return origin === '' ? path : `${origin}${path}`;
};

/**
 * The one instance, or null in bearer mode. Built on first request so that
 * importing this module stays free.
 */
let client: AuthClient<unknown> | null = null;
let built = false;

/**
 * Test seam for the WebAuthn surface, since `AuthClient` fixes the adapter at
 * construction. Null in every real bundle, leaving the package default.
 */
let webAuthnAdapter: WebAuthnAdapter | null = null;

/**
 * Installs a WebAuthn stub for the passkey tests. Tests only, and must run
 * before the first `getIdentityClient()`.
 */
export const setWebAuthnAdapterForTests = (
  adapter: WebAuthnAdapter | null
): void => {
  webAuthnAdapter = adapter;
};

/**
 * The identity client, or null in bearer mode. Null rather than a throw so a
 * panel can render its own unavailable state from the same code path.
 */
export const getIdentityClient = (): AuthClient<unknown> | null => {
  if (built) return client;
  built = true;
  if (AUTH_MODE !== 'identity') return null;
  const origin = identityOriginFrom(appConfig.apiBaseUrl);
  client = createAuthClient({
    baseUrl: origin === '' ? globalThis.location.origin : origin,
    clientOptions: {
      credentials: 'include',
      timeoutMs: 30000,
    },
    ...(webAuthnAdapter === null ? {} : { webAuthn: webAuthnAdapter }),
  });
  return client;
};

/**
 * Drops the cached instance. Tests only, and exported rather than done with
 * `vi.resetModules`, which would also drop `./client`'s shared client.
 */
export const resetIdentityClientForTests = (): void => {
  client?.dispose();
  client = null;
  built = false;
  webAuthnAdapter = null;
};
