/**
 * Tests for identity client construction and origin resolution.
 */

import { describe, expect, it, vi, afterEach } from 'vitest';
import { identityOriginFrom, getIdentityClient } from './identityClient';

afterEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

describe('identityOriginFrom', () => {
  it('strips a deployed API base back to its origin', () => {
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
    expect(identityOriginFrom('/api')).toBe('');
  });

  it('returns an empty base for a bare slash', () => {
    expect(identityOriginFrom('/')).toBe('');
  });

  it('returns a malformed value unchanged', () => {
    expect(identityOriginFrom('not a url')).toBe('not a url');
  });

  it('never produces a base that would double the api prefix', () => {
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
    expect(fresh()).toBe(first);
  });

  it('is a no-op to call repeatedly in bearer mode', () => {
    expect(getIdentityClient()).toBe(getIdentityClient());
  });
});
