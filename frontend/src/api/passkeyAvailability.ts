/**
 * Reads `GET /api/auth/passkeys/availability` to learn what this deployment
 * does with passkeys. `enabled` gates registering one, `passwordless` gates
 * offering it as a way in; the route guarantees the latter implies the former.
 */
import { type Availability, cachedAvailability } from './availabilityCache';

export { resetAvailabilityCache } from './availabilityCache';

/** Where the discovery route lives, relative to the identity origin. */
export const PASSKEY_AVAILABILITY_PATH = '/api/auth/passkeys/availability';

/**
 * What the route says this deployment does with passkeys. Tri-state rather than
 * boolean so an unreachable route is not read as a capability being off.
 */
export interface PasskeyCapabilities {
  /** Whether passkeys can be registered and verified here. */
  enabled: Availability;
  /** Whether a passkey is a way into an account here. */
  passwordless: Availability;
}

/** Nothing was learned, so nothing is offered. */
const UNKNOWN: PasskeyCapabilities = {
  enabled: 'unknown',
  passwordless: 'unknown',
};

/**
 * Parses the route body into the two answers. Any unrecognised shape yields
 * `unknown`, since learning nothing is not the same as a capability being off.
 */
export function parseCapabilities(body: unknown): PasskeyCapabilities {
  if (typeof body !== 'object' || body === null) return UNKNOWN;
  const { enabled, passwordless } = body as {
    enabled?: unknown;
    passwordless?: unknown;
  };
  if (typeof enabled !== 'boolean' || typeof passwordless !== 'boolean') {
    return UNKNOWN;
  }
  return {
    enabled: enabled ? 'available' : 'unavailable',
    passwordless: passwordless ? 'available' : 'unavailable',
  };
}

/**
 * Reads the discovery route uncredentialed. Every failure mode, a 404 from an
 * older backend included, is `unknown` rather than `unavailable`.
 */
export async function fetchPasskeyCapabilities(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<PasskeyCapabilities> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: 'GET',
      credentials: 'omit',
      headers: { accept: 'application/json' },
    });
  } catch {
    return UNKNOWN;
  }
  if (response.status !== 200) return UNKNOWN;
  try {
    return parseCapabilities(await response.json());
  } catch {
    return UNKNOWN;
  }
}

/**
 * The full answers, keyed to match the shared availability cache, so one cache
 * owns the eviction and coalescing rules rather than two that can disagree.
 */
const answers = new Map<string, PasskeyCapabilities>();

/** Drops the memoised answers. Tests only. */
export function resetPasskeyCapabilitiesForTests(): void {
  answers.clear();
}

/**
 * What this deployment does with passkeys, fetched at most once per page load
 * and keyed by full URL. An entry that learned nothing is evicted to retry.
 */
export function passkeyCapabilities(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<PasskeyCapabilities> {
  return cachedAvailability(url, async () => {
    const capabilities = await fetchPasskeyCapabilities(url, fetchImpl);
    if (capabilities.passwordless === 'unknown') {
      return 'unknown';
    }
    answers.set(url, capabilities);
    return capabilities.passwordless;
  }).then(() => answers.get(url) ?? UNKNOWN);
}

/** Whether passwordless passkey sign in is offered here. */
export function passkeyLoginAvailability(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<Availability> {
  return passkeyCapabilities(url, fetchImpl).then(
    (capabilities) => capabilities.passwordless
  );
}

/**
 * Whether passkeys can be registered here at all. Shares one request with
 * {@link passkeyLoginAvailability}.
 */
export function passkeyEnrolmentAvailability(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<Availability> {
  return passkeyCapabilities(url, fetchImpl).then(
    (capabilities) => capabilities.enabled
  );
}
