/**
 * The `@webbpulse/auth` client, constructed once when this bundle runs in
 * identity mode and never when it does not.
 *
 * Kept in its own module rather than inside `./client` for one reason: import
 * order. `./client` is imported by roughly ninety modules and by most of the
 * test suite, and constructing an `AuthClient` at its top level would put a
 * timer-scheduling, network-capable object into every one of those imports even
 * in bearer mode, where it has nothing to do. Here the construction is lazy and
 * the module is a leaf, so bearer mode pays for a null check and nothing else.
 *
 * ## What this does not do
 *
 * It does not decide *when* to refresh, retry a 401, or hold the token. All
 * three live inside `AuthClient` and are reached by handing the instance to
 * `createApiClient` as `auth`, which is what `./client` does. This module only
 * builds the thing and hands it out.
 */
import {
  createAuthClient,
  type AuthClient,
  type WebAuthnAdapter,
} from '@webbpulse/auth';
import { AUTH_MODE } from './authMode';
import { appConfig } from '../config/app';

/**
 * The origin the identity routes hang off, derived from the API base URL.
 *
 * Two different mount points on one host, and the difference is the whole
 * reason this function exists. This application's own routes live under `/api`,
 * which is what `appConfig.apiBaseUrl` carries. The identity service mounts at
 * the issuer's path, `/api/auth`, and `AuthClient`'s default paths are already
 * absolute (`/api/auth/login` and the rest).
 *
 * `joinUrl` in `@webbpulse/api-client` concatenates rather than resolving, so
 * handing `AuthClient` the `/api` base would send every identity call to
 * `/api/api/auth/login` and every one of them would 404. Stripping back to the
 * origin is what makes the package's own defaults land on the right routes,
 * which is why no path overrides are passed anywhere in this file.
 *
 * Three shapes reach this function, because CarModPicker's base URL is not
 * always absolute:
 *
 *   - `https://api.carmodpicker.com/api` in a deployed bundle, where the API
 *     is a separate host. Parses, and the origin is what is wanted.
 *   - `/api` in dev, where Vite proxies to the backend on the same origin.
 *     Does not parse on its own, and the right answer is the empty string:
 *     a request to `/api/auth/login` then goes to the page's own origin and
 *     through the same proxy.
 *   - Anything malformed, which is returned unchanged so a bad configuration
 *     fails visibly at the request rather than throwing at module load.
 */
export const identityOriginFrom = (apiBaseUrl: string): string => {
  try {
    return new URL(apiBaseUrl).origin;
  } catch {
    // A root-relative base means the API shares the page's origin, so the
    // identity routes do too and an empty base is exactly right.
    if (apiBaseUrl.startsWith('/')) return '';
    return apiBaseUrl;
  }
};

/**
 * An absolute URL for one identity route.
 *
 * The capability gates in `./oauthProviders` and `./passkeyAvailability` make
 * their own `fetch` calls rather than going through `AuthClient`, because both
 * read a discovery route before there is a session and neither wants the
 * retry-on-401 pipeline. They still have to reach the same origin the client would, so the
 * origin derivation lives here rather than being repeated twice.
 *
 * `path` is already absolute from the identity root (`/api/auth/...`), matching
 * the package's own defaults, so this only prefixes the origin.
 */
export const identityUrl = (path: string): string => {
  const origin = identityOriginFrom(appConfig.apiBaseUrl);
  return origin === '' ? path : `${origin}${path}`;
};

/**
 * The one instance, or null in bearer mode.
 *
 * Built on first request rather than at module load so that importing this
 * module is free, which matters because `./client` imports it unconditionally.
 */
let client: AuthClient<unknown> | null = null;
let built = false;

/**
 * The WebAuthn surface the passkey ceremonies run against, when one is set.
 *
 * `AuthClient` takes the adapter as a **constructor** option and defaults it to
 * `navigator.credentials`, so there is no per-call seam and this is the only
 * place a test can get one in. A jsdom run has no authenticator and cannot
 * produce a real credential, so `src/api/identityPasskeys.test.ts` sets a stub
 * here before the client is built and clears it after.
 *
 * Null in every real bundle, which leaves the package on its own default and
 * means production behaviour does not depend on this existing.
 */
let webAuthnAdapter: WebAuthnAdapter | null = null;

/**
 * Installs a WebAuthn stub for the passkey tests. Tests only.
 *
 * Must be called before the first `getIdentityClient()`, since the adapter is
 * fixed at construction. `resetIdentityClientForTests` clears it along with the
 * instance, so one test's stub cannot leak into the next.
 */
export const setWebAuthnAdapterForTests = (
  adapter: WebAuthnAdapter | null
): void => {
  webAuthnAdapter = adapter;
};

/**
 * The identity client, or null when this bundle runs the legacy bearer flow.
 *
 * Every caller has to handle null. That is deliberate: the alternative is a
 * throw, and a component that renders a TOTP panel would then have to be
 * mounted only under a mode check somewhere else. A null return lets the panel
 * itself say "not available in this deployment" from the same code path.
 */
export const getIdentityClient = (): AuthClient<unknown> | null => {
  if (built) return client;
  built = true;
  if (AUTH_MODE !== 'identity') return null;
  // The origin, not `appConfig.apiBaseUrl`. See `identityOriginFrom`.
  //
  // An empty origin means the API shares the page's origin, which is the dev
  // and same-host case. `createAuthClient` rejects an empty `baseUrl` outright
  // ("requires either baseUrl or an existing client"), so the page's own origin
  // is named explicitly rather than left implicit. That resolves to exactly the
  // same requests, and keeps the one code path that would otherwise throw at
  // first use in a dev bundle from ever being reached.
  const origin = identityOriginFrom(appConfig.apiBaseUrl);
  client = createAuthClient({
    baseUrl: origin === '' ? globalThis.location.origin : origin,
    clientOptions: {
      // The refresh token is an httpOnly cookie the page cannot read, so the
      // refresh call only works if the browser is told to send it. This is
      // load bearing rather than incidental.
      credentials: 'include',
      timeoutMs: 30000,
    },
    // Null in every real bundle, which leaves the package on its
    // `navigator.credentials` default. See `setWebAuthnAdapterForTests`.
    ...(webAuthnAdapter === null ? {} : { webAuthn: webAuthnAdapter }),
    // Deliberately no `loadUser`. `AuthClient` would call it after every
    // successful login and refresh, and this application already has one place
    // that fetches the user, `AuthContext.checkAuthStatus`, which reads roughly
    // twenty `UserRead` fields that no token claim carries. Two fetchers for
    // one thing is how the two copies drift.
  });
  return client;
};

/**
 * Drops the cached instance. Tests only.
 *
 * Exported rather than reached through a module reset because `vi.resetModules`
 * would also drop `./client`'s shared client, which most of the suite holds a
 * reference to.
 */
export const resetIdentityClientForTests = (): void => {
  client?.dispose();
  client = null;
  built = false;
  webAuthnAdapter = null;
};
