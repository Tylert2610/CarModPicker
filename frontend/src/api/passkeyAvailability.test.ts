// The passwordless passkey sign in probe.
//
// Each status is driven directly through `probePasskeyLogin` rather than
// through the cached wrapper, because the cache is the thing that makes a
// second call unobservable and a test of the classification needs every case to
// actually run.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  PASSKEY_LOGIN_OPTIONS_PATH,
  passkeyLoginAvailability,
  probePasskeyLogin,
} from './passkeyAvailability';
import { resetAvailabilityCache } from './availabilityCache';

const URL_UNDER_TEST = `https://api.test${PASSKEY_LOGIN_OPTIONS_PATH}`;

const answering = (status: number, body: unknown = {}) =>
  vi.fn().mockResolvedValue({
    status,
    json: () => Promise.resolve(body),
  });

beforeEach(() => {
  resetAvailabilityCache();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('probePasskeyLogin', () => {
  it('reads a challenge as available', async () => {
    await expect(
      probePasskeyLogin(URL_UNDER_TEST, answering(200, { challenge: 'x' }))
    ).resolves.toBe('available');
  });

  it('reads an unmounted route as unavailable', async () => {
    await expect(
      probePasskeyLogin(URL_UNDER_TEST, answering(404))
    ).resolves.toBe('unavailable');
  });

  it('reads the capability being off as unavailable', async () => {
    for (const code of ['PASSKEYS_DISABLED', 'PASSKEY_LOGIN_DISABLED']) {
      resetAvailabilityCache();
      await expect(
        probePasskeyLogin(URL_UNDER_TEST, answering(403, { error_code: code }))
      ).resolves.toBe('unavailable');
    }
  });

  it('reads some other refusal as unknown, not as unavailable', async () => {
    // A refusal this probe does not recognise says nothing about whether the
    // capability is configured, and telling a user it is gone would be a guess.
    await expect(
      probePasskeyLogin(
        URL_UNDER_TEST,
        answering(400, { error_code: 'VALIDATION_ERROR' })
      )
    ).resolves.toBe('unknown');
  });

  it('reads rate limiting as unknown', async () => {
    await expect(
      probePasskeyLogin(URL_UNDER_TEST, answering(429))
    ).resolves.toBe('unknown');
  });

  it('reads a network failure as unknown', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('offline'));
    await expect(probePasskeyLogin(URL_UNDER_TEST, fetchImpl)).resolves.toBe(
      'unknown'
    );
  });

  it('probes anonymously and without a username', async () => {
    // An address would be a discoverable-credential request for a specific
    // account. The probe is asking about the deployment, not about a user.
    const fetchImpl = answering(200, {});
    await probePasskeyLogin(URL_UNDER_TEST, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith(
      URL_UNDER_TEST,
      expect.objectContaining({
        method: 'POST',
        credentials: 'omit',
        body: '{}',
      })
    );
  });
});

describe('passkeyLoginAvailability', () => {
  it('probes once for two callers in the same tick', async () => {
    const fetchImpl = answering(200, {});
    await Promise.all([
      passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl),
      passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('keeps an unavailable answer, which is a deployment fact', async () => {
    const fetchImpl = answering(404);
    await passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl);
    await passkeyLoginAvailability(URL_UNDER_TEST, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('probes again after an answer that learned nothing', async () => {
    const failing = vi.fn().mockRejectedValue(new TypeError('offline'));
    await passkeyLoginAvailability(URL_UNDER_TEST, failing);
    const succeeding = answering(200, {});
    await expect(
      passkeyLoginAvailability(URL_UNDER_TEST, succeeding)
    ).resolves.toBe('available');
  });
});
