// Startup configuration, validated through @webbpulse/config.
//
// `loadAppConfig` does all of it now: it selects the backend for a dev run,
// appends the `/api` prefix the backend mounts every router under, rejects a
// malformed or non-http URL, normalises the Vite mode to an environment name,
// and reports every problem at once rather than failing later at the first
// request against an `undefined` URL.
//
// The selection used to be local. `@webbpulse/config` 0.2.0 could not describe
// this application's configuration, so a `resolveApiBaseUrl` here read
// `VITE_BACKEND`, picked one of three URLs and glued `/api` on the end, which
// put the one piece of URL selection outside the layer that exists to validate
// it. 0.3.0 added `backendTargets` and `apiPathPrefix` for exactly this, so the
// resolution is now two options rather than forty lines.
import { loadAppConfig, type AppConfig } from '@webbpulse/config';

/**
 * Reads a URL variable, treating blank as unset.
 *
 * `backendTargets` accepts `undefined` for a target and falls through to the
 * normal resolution, so an unset `VITE_STAGING_API_URL` needs no guard at the
 * call site. What it does not do is distinguish `''` from unset, hence this.
 */
const readEnvUrl = (env: ImportMetaEnv, key: string): string | undefined => {
  const value: unknown = env[key];
  return typeof value === 'string' && value.trim() !== ''
    ? value.trim()
    : undefined;
};

/**
 * Ensures a protocol on a URL from the environment.
 *
 * The deploy writes `VITE_API_URL` and the two dev URLs from the Terraform
 * `api_url` output, which is a bare host in some environments. The `/api`
 * suffix is no longer added here: `apiPathPrefix` below appends it after
 * resolution, and appending it twice would produce `/api/api`.
 */
const withProtocol = (url: string | undefined): string | undefined => {
  if (url === undefined) return undefined;
  return url.startsWith('http://') || url.startsWith('https://')
    ? url
    : `https://${url}`;
};

/**
 * Loads and validates the configuration for a given environment bag.
 *
 * Exported separately from the singleton below so tests can drive it with a
 * synthetic bag rather than the real `import.meta.env`.
 *
 * `backendTargets` is consulted by the package only when `DEV` is true, which
 * is what keeps a stray `VITE_BACKEND` in a deploy environment from repointing
 * a shipped production bundle at another backend. A dev run with no
 * `VITE_BACKEND`, or one naming a target whose URL is unset, falls through to
 * `defaultApiBaseUrl` and so to `/api`, which the Vite dev server proxies to
 * localhost:8000 and which is what keeps the session cookie same origin.
 */
export const loadCarModPickerConfig = (env: ImportMetaEnv): AppConfig =>
  loadAppConfig(
    {
      ...env,
      VITE_API_BASE_URL: withProtocol(readEnvUrl(env, 'VITE_API_URL')),
    },
    {
      defaultApiBaseUrl: '/api',
      defaultAppName: 'CarModPicker',
      backendTargets: {
        staging: withProtocol(readEnvUrl(env, 'VITE_STAGING_API_URL')),
        production: withProtocol(readEnvUrl(env, 'VITE_PROD_API_URL')),
      },
      apiPathPrefix: '/api',
    }
  );

/** The resolved configuration this bundle holds for its lifetime. */
export const appConfig: AppConfig = loadCarModPickerConfig(import.meta.env);
