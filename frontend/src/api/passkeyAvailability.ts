/**
 * What this deployment does with passkeys, read from the discovery route.
 *
 * ## Why this is a read rather than a probe
 *
 * An earlier revision of this file probed
 * `POST /api/auth/login/passkey/options` and classified the answer, because
 * when it was written there was no discovery route and the only observable
 * difference between "passkey sign in works here" and "it does not" was what
 * that route said. The note in that revision asked for exactly the route this
 * module now reads.
 *
 * webbpulse-python 0.17.0 added it. `GET /api/auth/passkeys/availability` is
 * mounted in every deployment, including one with passkeys switched off, needs
 * no credentials, and answers the two facts outright:
 *
 * ```json
 * { "enabled": true, "passwordless": false }
 * ```
 *
 * It carries `Cache-Control: public, max-age=300`, so repeat sign in page loads
 * mostly do not reach the function at all.
 *
 * ## What the probe cost, and why it is gone
 *
 * The probe spent one of the login options route's thirty calls per fifteen
 * minutes per IP on a sign in *page load* rather than on a sign in, so a user
 * who reloaded enough times was refused the passkey sign in they were reloading
 * in order to attempt. And it was not a read: the options route writes a
 * WebAuthn challenge row per call, so every page load left a row to expire, a
 * storage cost paid to answer a question about configuration.
 *
 * ## The two fields are different questions
 *
 * `enabled` means this deployment registers and verifies passkeys at all, so a
 * settings panel can offer to add one. `passwordless` means a passkey is a way
 * *into* an account, so the sign in page can offer the button. With `enabled`
 * true and `passwordless` false a passkey is a managed credential and a second
 * factor but not an entry point, which is the state production starts in.
 *
 * The package gates `passwordless` against `enabled` in the route itself, so
 * the pair is never `enabled: false` with `passwordless: true` and a caller can
 * read `passwordless` alone.
 *
 * Mirrors WebbPulse-Portfolio's `services/passkeyAvailability.ts`, which reads
 * the same route the same way.
 */
import { type Availability, cachedAvailability } from './availabilityCache';

export { resetAvailabilityCache } from './availabilityCache';

/** Where the discovery route lives, relative to the identity origin. */
export const PASSKEY_AVAILABILITY_PATH = '/api/auth/passkeys/availability';

/**
 * What the route says this deployment does with passkeys.
 *
 * Both fields are tri-state through `Availability` rather than booleans,
 * because "the route could not be reached" is not "the capability is off" and
 * a caller that collapses the two hides an affordance for the life of a page
 * over one dropped request.
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
 * Reads the route's body into the two answers, tolerating any shape.
 *
 * A body that is not an object, or whose fields are not booleans, is a backend
 * answering something this bundle does not understand. That is `unknown` rather
 * than `unavailable`: a malformed body is a reason to learn nothing, not a
 * reason to state that a capability is off.
 *
 * Exported for the test, which drives the parse directly rather than through a
 * stubbed `fetch`.
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
 * Reads the discovery route once.
 *
 * Every failure mode is `unknown`. A 404 is the one case worth naming: the
 * route mounts in every deployment from 0.17.0 onwards, so a 404 means a
 * backend older than that rather than a capability that is off, and reading it
 * as "off" would be the same ambiguity the probe had. Hiding the affordance is
 * what both answers produce anyway, and not caching the negative is what lets a
 * deploy under an open page be picked up on the next mount.
 *
 * Not credentialed. Discovery is anonymous, and sending the refresh cookie to a
 * route that does not read it is a habit worth not forming.
 *
 * Exported for the test, which drives it directly rather than through the
 * cache: the cache is the thing that makes a second call unobservable, and a
 * test of the classification needs each case to actually run.
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
    // A network failure, or the request being blocked. Nothing was learned.
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
 * The answers, memoised alongside the shared cache's tri-state.
 *
 * Same shape as `./oauthProviders`: `./availabilityCache` holds one
 * `Availability` per key and owns the once-per-page-load and coalescing rules,
 * and the richer value it was fetched with sits here under the same key. One
 * cache with one eviction rule rather than two that can disagree.
 */
const answers = new Map<string, PasskeyCapabilities>();

/** Drops the memoised answers. Tests only. */
export function resetPasskeyCapabilitiesForTests(): void {
  answers.clear();
}

/**
 * What this deployment does with passkeys, fetched at most once per page load.
 *
 * The cache key is the full URL, which folds the API origin in, and the entry
 * is evicted when nothing was learned so the next ask tries again. Two
 * components asking on the same paint join one request rather than making two.
 */
export function passkeyCapabilities(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<PasskeyCapabilities> {
  return cachedAvailability(url, async () => {
    const capabilities = await fetchPasskeyCapabilities(url, fetchImpl);
    if (capabilities.passwordless === 'unknown') {
      // Both fields are unknown together or neither is, so this one field
      // stands for the pair. Nothing worth remembering, and re-asking on the
      // next mount is cheap.
      return 'unknown';
    }
    answers.set(url, capabilities);
    // The cached tri-state is `passwordless`, which is what the sign in gate
    // reads. A deployment that answered at all is a fact that does not change
    // under the page, so it is kept either way.
    return capabilities.passwordless;
  }).then(() => answers.get(url) ?? UNKNOWN);
}

/**
 * Whether passwordless passkey sign in is offered here.
 *
 * The sign in page's gate, and the one field it may read: see the module note
 * on why `passwordless` stands alone.
 */
export function passkeyLoginAvailability(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<Availability> {
  return passkeyCapabilities(url, fetchImpl).then(
    (capabilities) => capabilities.passwordless
  );
}

/**
 * Whether passkeys can be registered here at all.
 *
 * The settings panel's question rather than the sign in page's. Shares the one
 * request with {@link passkeyLoginAvailability}, so a page that asks both asks
 * the network once.
 *
 * `../components/profile/IdentityPasskeySettings` does not call this: it lists
 * the account's credentials on mount and a deployment with passkeys off refuses
 * that call with a sentence the panel already renders, so reading `enabled`
 * there would be a second request answering a question the first one settles.
 */
export function passkeyEnrolmentAvailability(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<Availability> {
  return passkeyCapabilities(url, fetchImpl).then(
    (capabilities) => capabilities.enabled
  );
}
