/**
 * The one-read-per-page-load cache the capability gates share.
 *
 * ## Why there is a cache at all
 *
 * Whether a deployment has OAuth providers configured, and what it does with
 * passkeys, are both facts the bundle can only learn by asking the backend.
 * Each is a real request, and a login screen that re-asked on every render
 * would make one per keystroke while a user typed a password.
 *
 * ## Why promises are cached rather than results
 *
 * Two components asking in the same tick is the ordinary case rather than the
 * edge one: the login form and its passkey button both ask on first paint.
 * Caching the in-flight promise makes the second ask join the first request
 * instead of racing it, which is the difference between one read and two.
 *
 * ## Why `unknown` is not cached
 *
 * A read that failed on a flaky network learned nothing. Caching that answer
 * would hide the affordance for the life of the page over one dropped request,
 * so an `unknown` result is evicted as it resolves and the next ask reads
 * again. `unavailable` is a deployment fact and does not change under the page,
 * so it is kept.
 *
 * Shared with WebbPulse-Portfolio's `services/availabilityCache.ts`, which
 * solves the same problem the same way.
 */

/**
 * What one read concluded.
 *
 * `unknown` is deliberately not `unavailable`: it is what a network failure or
 * a CORS surprise leaves behind, and a caller renders nothing rather than
 * telling a user a capability is off when the read simply could not be made.
 */
export type Availability = 'available' | 'unavailable' | 'unknown';

/**
 * Keyed by the full requested URL, which folds the API origin into the key:
 * two bundles pointed at different backends cannot share an answer.
 */
const cache = new Map<string, Promise<Availability>>();

/** Empties the cache. For tests only. */
export function resetAvailabilityCache(): void {
  cache.clear();
}

/**
 * Runs `read` at most once per key per page load.
 *
 * See the file note for why the promise rather than the result is stored and
 * why an `unknown` answer is evicted.
 */
export function cachedAvailability(
  key: string,
  read: () => Promise<Availability>
): Promise<Availability> {
  const cached = cache.get(key);
  if (cached !== undefined) {
    return cached;
  }
  const pending = read().then((result) => {
    if (result === 'unknown') {
      cache.delete(key);
    }
    return result;
  });
  cache.set(key, pending);
  return pending;
}
