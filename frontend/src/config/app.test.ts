import { describe, expect, it } from 'vitest';
import { loadCarModPickerConfig } from './app';

/** A minimal env bag; only the keys under test need to be present. */
const env = (values: Record<string, unknown>): ImportMetaEnv => ({
  DEV: false,
  PROD: true,
  SSR: false,
  MODE: 'production',
  BASE_URL: '/',
  ...values,
});

/** A dev bag, since the backend switch is only consulted when DEV is true. */
const devEnv = (values: Record<string, unknown>): ImportMetaEnv =>
  env({ DEV: true, PROD: false, MODE: 'development', ...values });

const baseUrl = (values: ImportMetaEnv): string =>
  loadCarModPickerConfig(values).apiBaseUrl;

describe('the dev backend switch', () => {
  it('resolves the staging URL when DEV and VITE_BACKEND=staging', () => {
    expect(
      baseUrl(
        devEnv({
          VITE_BACKEND: 'staging',
          VITE_STAGING_API_URL: 'staging.example.com',
        })
      )
    ).toBe('https://staging.example.com/api');
  });

  it('resolves the production URL when DEV and VITE_BACKEND=production', () => {
    expect(
      baseUrl(
        devEnv({
          VITE_BACKEND: 'production',
          VITE_PROD_API_URL: 'prod.example.com',
        })
      )
    ).toBe('https://prod.example.com/api');
  });

  it('matches the backend name case insensitively', () => {
    expect(
      baseUrl(
        devEnv({
          VITE_BACKEND: 'STAGING',
          VITE_STAGING_API_URL: 'staging.example.com',
        })
      )
    ).toBe('https://staging.example.com/api');
  });

  it('defaults to /api in dev with no VITE_BACKEND override', () => {
    expect(baseUrl(devEnv({ VITE_BACKEND: '' }))).toBe('/api');
  });

  it('falls back to /api in dev when the named backend has no URL set', () => {
    expect(
      baseUrl(devEnv({ VITE_BACKEND: 'staging', VITE_STAGING_API_URL: '' }))
    ).toBe('/api');
  });

  it('falls back to /api in dev when VITE_BACKEND names no known target', () => {
    expect(baseUrl(devEnv({ VITE_BACKEND: 'nonsense' }))).toBe('/api');
  });

  it('ignores a stray VITE_BACKEND in a production build', () => {
    expect(
      baseUrl(
        env({
          VITE_BACKEND: 'staging',
          VITE_STAGING_API_URL: 'staging.example.com',
          VITE_API_URL: 'api.prod.example.com',
        })
      )
    ).toBe('https://api.prod.example.com/api');
  });
});

describe('the production API URL', () => {
  it('uses VITE_API_URL in a production build', () => {
    expect(baseUrl(env({ VITE_API_URL: 'api.prod.example.com' }))).toBe(
      'https://api.prod.example.com/api'
    );
  });

  it('falls back to /api in a production build with no VITE_API_URL', () => {
    expect(baseUrl(env({ VITE_API_URL: '' }))).toBe('/api');
  });

  it('preserves an explicit https:// protocol', () => {
    expect(baseUrl(env({ VITE_API_URL: 'https://secure.example.com' }))).toBe(
      'https://secure.example.com/api'
    );
  });

  it('preserves an explicit http:// protocol', () => {
    expect(baseUrl(env({ VITE_API_URL: 'http://insecure.example.com' }))).toBe(
      'http://insecure.example.com/api'
    );
  });

  it('adds https:// to a bare host, which is how Terraform emits api_url', () => {
    expect(baseUrl(env({ VITE_API_URL: 'api.example.com' }))).toBe(
      'https://api.example.com/api'
    );
  });

  it('strips trailing slashes before appending the /api prefix', () => {
    expect(baseUrl(env({ VITE_API_URL: 'https://api.example.com///' }))).toBe(
      'https://api.example.com/api'
    );
  });

  it('does not append /api twice when the URL already carries it', () => {
    expect(baseUrl(env({ VITE_API_URL: 'https://api.example.com/api' }))).toBe(
      'https://api.example.com/api'
    );
  });
});
