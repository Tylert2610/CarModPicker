// Phase 8 plan 08-02: client.ts coverage tests.
//
// CRITICAL: setup.ts globally mocks `../api/client` via D-18 so other test
// files get a mocked apiClient. THIS test file must exercise the REAL client
// module — token helpers, interceptors, paramsSerializer, and env-driven
// baseURL resolution. Pattern copied from `src/lib/sentry.test.ts`: call
// `vi.doUnmock('./client')` + `vi.resetModules()` in beforeEach, then use
// dynamic `await import('./client')` inside each test so the real module
// (re-)evaluates with current stubbed env.
//
// See PATTERNS.md §8 for the canonical env-driven baseURL pattern.
//
// Lint note: tests below access the axios internal
// `interceptors.request.handlers[N].fulfilled` shape to directly drive the
// request/response interceptor functions. Axios does not type this on the
// public Axios surface, so we cast through `as any`. The runtime shape is
// stable across axios 1.x versions. Disable the relevant rules file-wide
// because the interceptor tests need this cast repeatedly.
/* eslint-disable @typescript-eslint/no-explicit-any,
   @typescript-eslint/no-unsafe-member-access,
   @typescript-eslint/no-unsafe-assignment,
   @typescript-eslint/no-unsafe-call */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('client.ts — token helpers (real module)', () => {
  beforeEach(() => {
    vi.doUnmock('./client');
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('setStoredToken writes to localStorage under access_token key', async () => {
    const { setStoredToken } = await import('./client');
    setStoredToken('abc-123');
    expect(localStorage.getItem('access_token')).toBe('abc-123');
  });

  it('getStoredToken returns the stored access_token', async () => {
    const { setStoredToken, getStoredToken } = await import('./client');
    setStoredToken('round-trip');
    expect(getStoredToken()).toBe('round-trip');
  });

  it('getStoredToken returns null when no token is stored', async () => {
    const { getStoredToken } = await import('./client');
    expect(getStoredToken()).toBeNull();
  });

  it('removeStoredToken clears the stored access_token', async () => {
    const { setStoredToken, getStoredToken, removeStoredToken } =
      await import('./client');
    setStoredToken('to-be-removed');
    removeStoredToken();
    expect(getStoredToken()).toBeNull();
  });
});

describe('client.ts — credentials (real module)', () => {
  beforeEach(() => {
    vi.doUnmock('./client');
    vi.resetModules();
  });

  // Staging sits behind the access gate. Its CloudFront signed cookies are set
  // on the staging apex, so a call from www.staging to api.staging only carries
  // them when the client asks for credentials. Without this the gated staging
  // API answers 401.
  it('sends credentials so cross-subdomain cookies reach the API host', async () => {
    const { apiClient } = await import('./client');
    expect(apiClient.defaults.withCredentials).toBe(true);
  });
});

describe('client.ts — paramsSerializer (real module)', () => {
  beforeEach(() => {
    vi.doUnmock('./client');
    vi.resetModules();
  });

  it('expands array values as repeated keys (ids=1&ids=2&ids=3)', async () => {
    const { apiClient } = await import('./client');
    const serializer = apiClient.defaults.paramsSerializer as
      | ((p: Record<string, unknown>) => string)
      | { serialize: (p: Record<string, unknown>) => string }
      | undefined;
    expect(serializer).toBeDefined();

    const serialize =
      typeof serializer === 'function'
        ? serializer
        : (serializer as { serialize: (p: Record<string, unknown>) => string })
            .serialize;

    expect(serialize({ ids: [1, 2, 3] })).toBe('ids=1&ids=2&ids=3');
  });

  it('passes URLSearchParams through via .toString()', async () => {
    const { apiClient } = await import('./client');
    const serializer = apiClient.defaults.paramsSerializer as
      ((p: unknown) => string) | { serialize: (p: unknown) => string };
    const serialize =
      typeof serializer === 'function' ? serializer : serializer.serialize;

    const usp = new URLSearchParams({ a: '1', b: '2' });
    expect(serialize(usp)).toBe('a=1&b=2');
  });

  it('skips undefined and null values but keeps falsy 0 / empty string', async () => {
    const { apiClient } = await import('./client');
    const serializer = apiClient.defaults.paramsSerializer as
      | ((p: Record<string, unknown>) => string)
      | { serialize: (p: Record<string, unknown>) => string };
    const serialize =
      typeof serializer === 'function' ? serializer : serializer.serialize;

    const result = serialize({
      a: 1,
      b: undefined,
      c: null,
      d: 0,
    });
    // undefined and null dropped; 0 kept
    expect(result).toBe('a=1&d=0');
  });

  it('URL-encodes special characters in scalar values', async () => {
    const { apiClient } = await import('./client');
    const serializer = apiClient.defaults.paramsSerializer as
      | ((p: Record<string, unknown>) => string)
      | { serialize: (p: Record<string, unknown>) => string };
    const serialize =
      typeof serializer === 'function' ? serializer : serializer.serialize;

    expect(serialize({ q: 'honda civic' })).toBe('q=honda%20civic');
  });
});

describe('client.ts — request interceptor (real module)', () => {
  beforeEach(() => {
    vi.doUnmock('./client');
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('attaches Authorization: Bearer <token> header when a token is stored', async () => {
    const { apiClient, setStoredToken } = await import('./client');
    setStoredToken('bearer-abc');

    const requestInterceptor = (apiClient.interceptors.request as any)
      .handlers[0].fulfilled;
    const config: any = { headers: {} };
    const result = await requestInterceptor(config);

    expect(result.headers.Authorization).toBe('Bearer bearer-abc');
  });

  it('does not attach Authorization header when no token is stored', async () => {
    const { apiClient } = await import('./client');

    const requestInterceptor = (apiClient.interceptors.request as any)
      .handlers[0].fulfilled;
    const config: any = { headers: {} };
    const result = await requestInterceptor(config);

    expect(result.headers.Authorization).toBeUndefined();
  });

  it('request interceptor rejected branch wraps non-Error into Error', async () => {
    const { apiClient } = await import('./client');

    const rejected = (apiClient.interceptors.request as any).handlers[0]
      .rejected;
    await expect(rejected('boom')).rejects.toThrow('boom');
  });
});

describe('client.ts — response interceptor (real module)', () => {
  beforeEach(() => {
    vi.doUnmock('./client');
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('stores x-new-access-token header into localStorage on success', async () => {
    const { apiClient, getStoredToken } = await import('./client');

    const responseInterceptor = (apiClient.interceptors.response as any)
      .handlers[0].fulfilled;
    const response: any = {
      headers: { 'x-new-access-token': 'rotated-token' },
      data: null,
    };
    await responseInterceptor(response);

    expect(getStoredToken()).toBe('rotated-token');
  });

  it('does not store anything when x-new-access-token header is absent', async () => {
    const { apiClient, getStoredToken } = await import('./client');

    const responseInterceptor = (apiClient.interceptors.response as any)
      .handlers[0].fulfilled;
    const response: any = { headers: {}, data: null };
    await responseInterceptor(response);

    expect(getStoredToken()).toBeNull();
  });

  it('response interceptor rejected branch does NOT redirect on 401 (behavior preserved)', async () => {
    const { apiClient } = await import('./client');

    const rejected = (apiClient.interceptors.response as any).handlers[0]
      .rejected;
    const err = { response: { status: 401 } };
    // window.location.href assignment commented out in client.ts per line ~132
    // — this test simply confirms the rejected handler rethrows the error.
    await expect(rejected(err)).rejects.toThrow();
  });
});

describe('client.ts — env-driven baseURL (real module)', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.doUnmock('./client');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('resolves staging URL when DEV=true and VITE_BACKEND=staging', async () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_BACKEND', 'staging');
    vi.stubEnv('VITE_STAGING_API_URL', 'staging.example.com');

    const { apiClient } = await import('./client');
    expect(apiClient.defaults.baseURL).toBe('https://staging.example.com/api');
  });

  it('resolves production URL when DEV=true and VITE_BACKEND=production', async () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_BACKEND', 'production');
    vi.stubEnv('VITE_PROD_API_URL', 'prod.example.com');

    const { apiClient } = await import('./client');
    expect(apiClient.defaults.baseURL).toBe('https://prod.example.com/api');
  });

  it('defaults to /api when DEV=true and no VITE_BACKEND override is set', async () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_BACKEND', '');

    const { apiClient } = await import('./client');
    expect(apiClient.defaults.baseURL).toBe('/api');
  });

  it('uses VITE_API_URL in production (DEV=false)', async () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_API_URL', 'api.prod.example.com');

    const { apiClient } = await import('./client');
    expect(apiClient.defaults.baseURL).toBe('https://api.prod.example.com/api');
  });

  it('falls back to /api in production when VITE_API_URL is not set', async () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_API_URL', '');

    const { apiClient } = await import('./client');
    expect(apiClient.defaults.baseURL).toBe('/api');
  });

  it('preserves explicit https:// protocol in normalizeApiUrl', async () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_API_URL', 'https://secure.example.com');

    const { apiClient } = await import('./client');
    expect(apiClient.defaults.baseURL).toBe('https://secure.example.com/api');
  });
});
