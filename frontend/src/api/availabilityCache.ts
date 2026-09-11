/**
 * One-read-per-page-load cache shared by the capability gates. Caches the
 * in-flight promise so concurrent asks join one request, and evicts `unknown`
 * so a dropped request does not hide an affordance for the life of the page.
 */

/**
 * What one read concluded. `unknown` means the read could not be made, which is
 * not the same as the capability being off.
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

/** Runs `read` at most once per key per page load. */
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
