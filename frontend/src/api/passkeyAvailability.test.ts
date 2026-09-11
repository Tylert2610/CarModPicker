// The passkey discovery route, and the two questions read off it.
//
// Each case is driven directly through `fetchPasskeyCapabilities` rather than
// through the cached wrapper, because the cache is the thing that makes a
// second call unobservable and a test of the classification needs every case to
// actually run.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  PASSKEY_AVAILABILITY_PATH,
  fetchPasskeyCapabilities,
  parseCapabilities,
  passkeyCapabilities,
  passkeyEnrolmentAvailability,
  passkeyLoginAvailability,
  resetPasskeyCapabilitiesForTests,
} from './passkeyAvailability';
import { resetAvailabilityCache } from './availabilityCache';

const URL_UNDER_TEST = `https://api.test${PASSKEY_AVAILABILITY_PATH}`;

const answering = (status: number, body: unknown = {}) =>
  vi.fn().mockResolvedValue({
    status,
    json: () => Promise.resolve(body),
  });

beforeEach(() => {
  resetAvailabilityCache();
  resetPasskeyCapabilitiesForTests();
});

afterEach(() => {
  vi.clearAllMocks();
  resetAvailabilityCache();
  resetPasskeyCapabilitiesForTests();
});

describe('parseCapabilities', () => {
  it('reads the two booleans', () => {
    expect(parseCapabilities({ enabled: true, passwordless: true })).toEqual({
      enabled: 'available',
      passwordless: 'available',
    });
  });

  it('reads passkeys on but not a way in', () => {
    // The state production starts in: a passkey is a managed credential and a
    // second factor, so the settings panel offers to add one and the sign in
    // button must not appear. The old probe could only see this as a
    // `PASSKEY_LOGIN_DISABLED` refusal; the route states it as a field.
    expect(parseCapabilities({ enabled: true, passwordless: false })).toEqual({
      enabled: 'available',
      passwordless: 'unavailable',
    });
  });

  it('reads the capability being off altogether', () => {
    expect(parseCapabilities({ enabled: false, passwordless: false })).toEqual({
      enabled: 'unavailable',
      passwordless: 'unavailable',
    });
  });

  it('reads a malformed body as unknown, not as unavailable', () => {
    // A backend answering something this bundle does not understand is a
    // reason to learn nothing, not a reason to state that a capability is off.
    for (const body of [
      null,
      'nope',
      {},
      { enabled: 'yes', passwordless: 'no' },
      { enabled: true },
    ]) {
      expect(parseCapabilities(body)).toEqual({
        enabled: 'unknown',
        passwordless: 'unknown',
      });
    }
  });
});

describe('fetchPasskeyCapabilities', () => {
  it('reads a 200 body', async () => {
    await expect(
      fetchPasskeyCapabilities(
        URL_UNDER_TEST,
        answering(200, { enabled: true, passwordless: true })
      )
    ).resolves.toEqual({ enabled: 'available', passwordless: 'available' });
  });

  it('reads an unmounted route as unknown, not as unavailable', async () => {
    // The route mounts in every deployment from 0.17.0 onwards, so a 404 means
    // a backend older than that rather than a capability that is off. Reading
    // it as "off" would be the ambiguity the probe had.
    await expect(
      fetchPasskeyCapabilities(URL_UNDER_TEST, answering(404))
    ).resolves.toEqual({ enabled: 'unknown', passwordless: 'unknown' });
  });

  it('reads any other non-200 as unknown', async () => {
    for (const status of [401, 429, 500, 503]) {
      await expect(
        fetchPasskeyCapabilities(URL_UNDER_TEST, answering(status))
      ).resolves.toEqual({ enabled: 'unknown', passwordless: 'unknown' });
    }
  });

  it('reads a network failure as unknown', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('offline'));
    await expect(
      fetchPasskeyCapabilities(URL_UNDER_TEST, fetchImpl)
    ).resolves.toEqual({ enabled: 'unknown', passwordless: 'unknown' });
  });

  it('reads a body that is not JSON as unknown', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.reject(new SyntaxError('not json')),
    });
    await expect(
      fetchPasskeyCapabilities(URL_UNDER_TEST, fetchImpl)
    ).resolves.toEqual({ enabled: 'unknown', passwordless: 'unknown' });
  });

  it('reads anonymously with a plain GET', async () => {
    // Discovery has no session by definition, and sending the refresh cookie
    // to a route that does not read it is a habit worth not forming.
    const fetchImpl = answering(200, { enabled: true, passwordless: true });
    await fetchPasskeyCapabilities(URL_UNDER_TEST, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith(
      URL_UNDER_TEST,
      expect.objectContaining({ method: 'GET', credentials: 'omit' })
    );
  });
});

describe('passkeyLoginAvailability', () => {
  it('is available only when the route says passwordless', async () => {
    await expect(
      passkeyLoginAvailability(
        URL_UNDER_TEST,
        answering(200, { enabled: true, passwordless: true })
      )
    ).resolves.toBe('available');
  });

  it('is unavailable where passkeys are on but not a way in', async () => {
    await expect(
      passkeyLoginAvailability(
        URL_UNDER_TEST,
        answering(200, { enabled: true, passwordless: false })
      )
    ).resolves.toBe('unavailable');
  });

  it('is unknown when nothing was learned', async () => {
    await expect(
      passkeyLoginAvailability(URL_UNDER_TEST, answering(404))
    ).resolves.toBe('unknown');
  });

  it('reads once for two callers in the same tick', async () => {
    const fetchImpl = answering(200, { enabled: true, passwordless: true });
    await Promise.all([
      passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl),
      passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('keeps an unavailable answer, which is a deployment fact', async () => {
    const fetchImpl = answering(200, { enabled: false, passwordless: false });
    await passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl);
    await passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('reads again after an answer that learned nothing', async () => {
    const failing = vi.fn().mockRejectedValue(new TypeError('offline'));
    await expect(
      passkeyLoginAvailability(URL_UNDER_TEST, failing)
    ).resolves.toBe('unknown');
    const succeeding = answering(200, { enabled: true, passwordless: true });
    await expect(
      passkeyLoginAvailability(URL_UNDER_TEST, succeeding)
    ).resolves.toBe('available');
  });
});

describe('passkeyEnrolmentAvailability', () => {
  it('is the other field of the same answer', async () => {
    await expect(
      passkeyEnrolmentAvailability(
        URL_UNDER_TEST,
        answering(200, { enabled: true, passwordless: false })
      )
    ).resolves.toBe('available');
  });

  it('shares the one request with the sign in gate', async () => {
    // A page that asks both questions asks the network once. This is the whole
    // reason the two fields come off one route rather than two.
    const fetchImpl = answering(200, { enabled: true, passwordless: false });
    const [login, enrolment] = await Promise.all([
      passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl),
      passkeyEnrolmentAvailability(URL_UNDER_TEST, fetchImpl),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(login).toBe('unavailable');
    expect(enrolment).toBe('available');
  });
});

describe('passkeyCapabilities', () => {
  it('hands back both fields together', async () => {
    await expect(
      passkeyCapabilities(
        URL_UNDER_TEST,
        answering(200, { enabled: true, passwordless: false })
      )
    ).resolves.toEqual({ enabled: 'available', passwordless: 'unavailable' });
  });
});
