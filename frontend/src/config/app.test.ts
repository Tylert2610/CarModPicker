// API base URL resolution, which used to be asserted through
// `apiClient.defaults.baseURL` in `api/client.test.ts`. The selection moved to
// this module when the transport moved to `@webbpulse/api-client`, so the tests
// moved with it and now read the resolved value directly.
//
// `resolveApiBaseUrl` is driven with a synthetic env bag rather than a stubbed
// `import.meta.env`, which is what lets a case set `DEV` and the URL variables
// independently without re-importing the module.
import { describe, expect, it } from 'vitest';
import { normalizeApiUrl, resolveApiBaseUrl } from './app';

/** A minimal env bag; only the keys under test need to be present. */
const env = (values: Record<string, unknown>): ImportMetaEnv => ({
  DEV: false,
  PROD: true,
  SSR: false,
  MODE: 'production',
  BASE_URL: '/',
  ...values,
});

describe('resolveApiBaseUrl', () => {
  it('resolves the staging URL when DEV and VITE_BACKEND=staging', () => {
    expect(
      resolveApiBaseUrl(
        env({
          DEV: true,
          VITE_BACKEND: 'staging',
          VITE_STAGING_API_URL: 'staging.example.com',
        })
      )
    ).toBe('https://staging.example.com/api');
  });

  it('resolves the production URL when DEV and VITE_BACKEND=production', () => {
    expect(
      resolveApiBaseUrl(
        env({
          DEV: true,
          VITE_BACKEND: 'production',
          VITE_PROD_API_URL: 'prod.example.com',
        })
      )
    ).toBe('https://prod.example.com/api');
  });

  it('defaults to /api in dev with no VITE_BACKEND override', () => {
    // The dev server proxies /api to localhost:8000, which is what keeps the
    // session cookie same origin during local development.
    expect(resolveApiBaseUrl(env({ DEV: true, VITE_BACKEND: '' }))).toBe(
      '/api'
    );
  });

  it('falls back to /api in dev when the named backend has no URL set', () => {
    expect(
      resolveApiBaseUrl(
        env({ DEV: true, VITE_BACKEND: 'staging', VITE_STAGING_API_URL: '' })
      )
    ).toBe('/api');
  });

  it('uses VITE_API_URL in a production build', () => {
    expect(
      resolveApiBaseUrl(env({ VITE_API_URL: 'api.prod.example.com' }))
    ).toBe('https://api.prod.example.com/api');
  });

  it('falls back to /api in a production build with no VITE_API_URL', () => {
    expect(resolveApiBaseUrl(env({ VITE_API_URL: '' }))).toBe('/api');
  });
});

describe('normalizeApiUrl', () => {
  it('preserves an explicit https:// protocol', () => {
    expect(normalizeApiUrl('https://secure.example.com')).toBe(
      'https://secure.example.com/api'
    );
  });

  it('preserves an explicit http:// protocol', () => {
    expect(normalizeApiUrl('http://insecure.example.com')).toBe(
      'http://insecure.example.com/api'
    );
  });

  it('adds https:// to a bare host, which is how Terraform emits api_url', () => {
    expect(normalizeApiUrl('api.example.com')).toBe(
      'https://api.example.com/api'
    );
  });

  it('strips trailing slashes before appending the /api prefix', () => {
    expect(normalizeApiUrl('https://api.example.com///')).toBe(
      'https://api.example.com/api'
    );
  });
});
