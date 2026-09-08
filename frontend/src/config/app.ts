// Startup configuration, validated through @webbpulse/config.
//
// The shared `loadAppConfig` does the validating: it rejects a malformed or
// non-http API base URL, strips a trailing slash, normalises the Vite mode to
// an environment name, and reports every problem at once rather than failing
// later at the first request against an `undefined` URL.
//
// What stays local is the *selection* of which URL to validate. CarModPicker
// has a dev-only backend switch (`VITE_BACKEND=local|staging|production`,
// behind `npm run dev:staging` / `dev:prod`) and appends the `/api` prefix the
// backend mounts every router under. Neither is modelled by the shared
// package, and both are load bearing, so the resolution below picks the raw
// URL and `loadAppConfig` validates the result.
import { loadAppConfig, type AppConfig } from '@webbpulse/config';

/**
 * Ensures a protocol and appends the `/api` prefix.
 *
 * The deploy writes `VITE_API_URL` from the Terraform `api_url` output, which
 * is a bare host in some environments, so the protocol is added when missing.
 */
const normalizeApiUrl = (url: string): string => {
  const urlWithProtocol =
    url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `https://${url}`;
  return `${urlWithProtocol.replace(/\/+$/, '')}/api`;
};

const readEnvUrl = (env: ImportMetaEnv, key: string): string | undefined => {
  const value: unknown = env[key];
  return typeof value === 'string' && value.trim() !== ''
    ? value.trim()
    : undefined;
};

/**
 * Picks the API base URL for this bundle, before validation.
 *
 * Returns `/api` for local development so requests go through the Vite dev
 * server proxy to localhost:8000, which is what keeps cookies same origin.
 */
const resolveApiBaseUrl = (env: ImportMetaEnv): string => {
  if (env.DEV) {
    const backend = readEnvUrl(env, 'VITE_BACKEND')?.toLowerCase() ?? 'local';
    if (backend === 'staging') {
      const stagingUrl = readEnvUrl(env, 'VITE_STAGING_API_URL');
      if (stagingUrl !== undefined) return normalizeApiUrl(stagingUrl);
    }
    if (backend === 'production') {
      const prodUrl = readEnvUrl(env, 'VITE_PROD_API_URL');
      if (prodUrl !== undefined) return normalizeApiUrl(prodUrl);
    }
    return '/api';
  }

  const apiUrl = readEnvUrl(env, 'VITE_API_URL');
  return apiUrl === undefined ? '/api' : normalizeApiUrl(apiUrl);
};

/**
 * Loads and validates the configuration for a given environment bag.
 *
 * Exported separately from the singleton below so tests can drive it with a
 * synthetic bag rather than the real `import.meta.env`.
 */
export const loadCarModPickerConfig = (env: ImportMetaEnv): AppConfig =>
  loadAppConfig(
    { ...env, VITE_API_BASE_URL: resolveApiBaseUrl(env) },
    { defaultApiBaseUrl: '/api', defaultAppName: 'CarModPicker' }
  );

/** The resolved configuration this bundle holds for its lifetime. */
export const appConfig: AppConfig = loadCarModPickerConfig(import.meta.env);

export { normalizeApiUrl, resolveApiBaseUrl };
