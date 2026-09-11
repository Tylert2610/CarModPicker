/**
 * Tests for OAuth provider discovery and caching.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  OAUTH_PROVIDERS_PATH,
  oauthProviders,
  parseProviders,
  providerLabel,
  resetProvidersForTests,
} from './oauthProviders';
import { resetAvailabilityCache } from './availabilityCache';

const URL_UNDER_TEST = `https://api.test${OAUTH_PROVIDERS_PATH}`;

/** A `fetch` that answers one JSON body with one status. */
const answering = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });

beforeEach(() => {
  resetAvailabilityCache();
  resetProvidersForTests();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('parseProviders', () => {
  it('reads id and display name', () => {
    expect(
      parseProviders({
        providers: [{ id: 'google', display_name: 'Google' }],
      })
    ).toEqual([{ id: 'google', displayName: 'Google' }]);
  });

  it('names a provider the server did not', () => {
    expect(parseProviders({ providers: [{ id: 'github' }] })).toEqual([
      { id: 'github', displayName: 'GitHub' },
    ]);
  });

  it('keeps a provider this build has never heard of', () => {
    expect(
      parseProviders({
        providers: [{ id: 'okta', display_name: 'Acme SSO' }],
      })
    ).toEqual([{ id: 'okta', displayName: 'Acme SSO' }]);
  });

  it('drops an entry with no usable id', () => {
    expect(
      parseProviders({
        providers: [{ display_name: 'Nameless' }, { id: '' }, null, 'google'],
      })
    ).toEqual([]);
  });

  it('reads nothing out of a body that is not the envelope', () => {
    expect(parseProviders(null)).toEqual([]);
    expect(parseProviders({})).toEqual([]);
    expect(parseProviders({ providers: 'google' })).toEqual([]);
  });
});

describe('providerLabel', () => {
  it('names the baseline providers', () => {
    expect(providerLabel('google')).toBe('Google');
    expect(providerLabel('github')).toBe('GitHub');
  });

  it('title cases anything else rather than showing a raw wire value', () => {
    expect(providerLabel('okta')).toBe('Okta');
  });
});

describe('oauthProviders', () => {
  it('returns the configured set', async () => {
    const fetchImpl = answering(200, {
      providers: [{ id: 'google', display_name: 'Google' }],
    });
    await expect(oauthProviders(URL_UNDER_TEST, fetchImpl)).resolves.toEqual([
      { id: 'google', displayName: 'Google' },
    ]);
  });

  it('returns nothing for a backend that predates the route', async () => {
    const fetchImpl = answering(404, {});
    await expect(oauthProviders(URL_UNDER_TEST, fetchImpl)).resolves.toEqual(
      []
    );
  });

  it('returns nothing when the network failed', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('offline'));
    await expect(oauthProviders(URL_UNDER_TEST, fetchImpl)).resolves.toEqual(
      []
    );
  });

  it('fetches once for two callers in the same tick', async () => {
    const fetchImpl = answering(200, {
      providers: [{ id: 'google', display_name: 'Google' }],
    });
    const [first, second] = await Promise.all([
      oauthProviders(URL_UNDER_TEST, fetchImpl),
      oauthProviders(URL_UNDER_TEST, fetchImpl),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(first).toEqual(second);
  });

  it('asks again after a read that learned nothing', async () => {
    const failing = vi.fn().mockRejectedValue(new TypeError('offline'));
    await oauthProviders(URL_UNDER_TEST, failing);
    const succeeding = answering(200, {
      providers: [{ id: 'google', display_name: 'Google' }],
    });
    await expect(oauthProviders(URL_UNDER_TEST, succeeding)).resolves.toEqual([
      { id: 'google', displayName: 'Google' },
    ]);
  });

  it('does not send credentials', async () => {
    const fetchImpl = answering(200, { providers: [] });
    await oauthProviders(URL_UNDER_TEST, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith(
      URL_UNDER_TEST,
      expect.objectContaining({ method: 'GET', credentials: 'omit' })
    );
  });
});
