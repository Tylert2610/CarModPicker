// The identity client and, mostly, the URL derivation it depends on.
//
// `identityOriginFrom` gets the bulk of the coverage because it is the one
// piece of this migration with a known, silent failure mode: `joinUrl` in
// `@webbpulse/api-client` concatenates rather than resolving, so handing
// `AuthClient` the `/api` base sends every identity call to `/api/api/auth/...`
// and every one of them 404s with nothing in the console to say why.
import { describe, expect, it, vi, afterEach } from 'vitest';
import { identityOriginFrom, getIdentityClient } from './identityClient';

afterEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

describe('identityOriginFrom', () => {
  it('strips a deployed API base back to its origin', () => {
    // The shape production runs: the API is its own host and the application
    // routes live under /api, but identity mounts at /api/auth on the origin.
    expect(identityOriginFrom('https://api.carmodpicker.com/api')).toBe(
      'https://api.carmodpicker.com'
    );
  });

  it('strips the staging API base back to its origin', () => {
    expect(identityOriginFrom('https://api.staging.carmodpicker.com/api')).toBe(
      'https://api.staging.carmodpicker.com'
    );
  });

  it('keeps a non default port', () => {
    expect(identityOriginFrom('http://localhost:8000/api')).toBe(
      'http://localhost:8000'
    );
  });

  it('returns an empty base for a root relative API base', () => {
    // The dev and same-origin shape. `/api` cannot be parsed as a URL, and the
    // right answer is an empty base so that `/api/auth/login` resolves against
    // the page's own origin and goes through the same Vite proxy.
    expect(identityOriginFrom('/api')).toBe('');
  });

  it('returns an empty base for a bare slash', () => {
    expect(identityOriginFrom('/')).toBe('');
  });

  it('returns a malformed value unchanged', () => {
    // Deliberately not a throw. A bad configuration should fail visibly at the
    // request rather than at module load, where it would take down every page
    // including the ones that need no auth.
    expect(identityOriginFrom('not a url')).toBe('not a url');
  });

  it('never produces a base that would double the api prefix', () => {
    // The regression this whole function exists to prevent. Whatever comes
    // back, appending the package's own absolute path must not yield
    // /api/api/auth.
    for (const base of [
      'https://api.carmodpicker.com/api',
      'http://localhost:8000/api',
      '/api',
    ]) {
      expect(identityOriginFrom(base) + '/api/auth/login').not.toContain(
        '/api/api/auth'
      );
    }
  });
});

describe('getIdentityClient', () => {
  it('returns null in bearer mode', async () => {
    // The default every environment runs today. A null client is what the
    // pages branch on to render their "not available in this deployment"
    // states, so this is load bearing rather than incidental.
    vi.stubEnv('VITE_AUTH_MODE', '');
    vi.resetModules();
    const { getIdentityClient: fresh } = await import('./identityClient');
    expect(fresh()).toBeNull();
  });

  it('returns null when the mode is explicitly bearer', async () => {
    vi.stubEnv('VITE_AUTH_MODE', 'bearer');
    vi.resetModules();
    const { getIdentityClient: fresh } = await import('./identityClient');
    expect(fresh()).toBeNull();
  });

  it('builds a client in identity mode and caches it', async () => {
    vi.stubEnv('VITE_AUTH_MODE', 'identity');
    vi.resetModules();
    const { getIdentityClient: fresh } = await import('./identityClient');
    const first = fresh();
    expect(first).not.toBeNull();
    // One instance for the bundle's lifetime. Two would each hold their own
    // access token and their own refresh timer, and a refresh through one
    // would leave the other holding a token the server has rotated away.
    expect(fresh()).toBe(first);
  });

  it('is a no-op to call repeatedly in bearer mode', () => {
    expect(getIdentityClient()).toBe(getIdentityClient());
  });
});
