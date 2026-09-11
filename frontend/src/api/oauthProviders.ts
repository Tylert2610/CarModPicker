/**
 * Which OAuth providers this deployment actually has configured.
 *
 * ## Why this is a read rather than a probe
 *
 * WebbPulse-Portfolio's `services/oauthAvailability.ts` probes each provider's
 * start route with `redirect: 'manual'` and classifies the answer, because when
 * it was written there was no discovery endpoint and the only observable
 * difference between "Google is configured" and "Google is not" was what
 * `GET /api/auth/oauth/google/start` answered. The note in that file asks for
 * exactly the route this module reads.
 *
 * webbpulse-python 0.16.0 added it. `GET /api/auth/oauth/providers` is always
 * mounted, needs no credentials, and answers the configured set outright:
 *
 * ```json
 * { "providers": [{ "id": "google", "display_name": "Google" }] }
 * ```
 *
 * So this is one uncredentialed GET instead of one probe per provider, it
 * spends no start rate limit bucket, it burns no challenge row, and the login
 * page can render the real set rather than intersecting a hardcoded list with
 * per-provider guesses. A provider this build has never heard of renders from
 * the server's own `display_name`.
 *
 * `@webbpulse/auth` 0.8.0 carries no helper for this route, so the fetch and
 * the parse are here. The provider id constants still come from the package,
 * so a rename in the standard is a compile error rather than a button that
 * silently 404s.
 */
import { GITHUB_PROVIDER, GOOGLE_PROVIDER } from '@webbpulse/auth';

import { cachedAvailability } from './availabilityCache';

export { resetAvailabilityCache } from './availabilityCache';

/** Where the discovery route lives, relative to the identity origin. */
export const OAUTH_PROVIDERS_PATH = '/api/auth/oauth/providers';

/**
 * One provider the backend says is configured.
 *
 * `displayName` is the server's, because the server is the only thing that
 * knows about a provider this bundle predates.
 */
export interface OAuthProvider {
  id: string;
  displayName: string;
}

/**
 * A human name for a provider when the server did not send one.
 *
 * Only the two in the standard's mandatory baseline are named here. Anything
 * else falls through to title case, which is better than rendering a raw
 * lowercase wire value.
 */
export function providerLabel(provider: string): string {
  switch (provider) {
    case GOOGLE_PROVIDER:
      return 'Google';
    case GITHUB_PROVIDER:
      return 'GitHub';
    default:
      return provider.charAt(0).toUpperCase() + provider.slice(1);
  }
}

/**
 * Reads the route's body into a provider list, tolerating any shape.
 *
 * An entry without a usable `id` is dropped rather than rendered as a button
 * that cannot start anything. A missing `display_name` falls back to
 * {@link providerLabel} so a terse server still produces a readable button.
 *
 * Exported for the test, which drives the parse directly rather than through a
 * stubbed `fetch`.
 */
export function parseProviders(body: unknown): OAuthProvider[] {
  if (typeof body !== 'object' || body === null) return [];
  const raw = (body as { providers?: unknown }).providers;
  if (!Array.isArray(raw)) return [];
  const providers: OAuthProvider[] = [];
  for (const entry of raw) {
    if (typeof entry !== 'object' || entry === null) continue;
    const id = (entry as { id?: unknown }).id;
    if (typeof id !== 'string' || id === '') continue;
    const name = (entry as { display_name?: unknown }).display_name;
    providers.push({
      id,
      displayName:
        typeof name === 'string' && name !== '' ? name : providerLabel(id),
    });
  }
  return providers;
}

/**
 * The providers the backend reports, or an empty list.
 *
 * An empty list is returned for every failure mode: a 404 means this backend
 * predates 0.16.0 and has no OAuth at all, and a network failure means nothing
 * was learned. Both render no buttons, which is the same thing a user sees on a
 * deployment with no providers configured, and is always safe: a button that
 * cannot work is worse than an absent one.
 *
 * Not credentialed. Discovery is anonymous, and sending the refresh cookie to a
 * route that does not read it is a habit worth not forming.
 */
export async function fetchProviders(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<OAuthProvider[]> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: 'GET',
      credentials: 'omit',
      headers: { accept: 'application/json' },
    });
  } catch {
    return [];
  }
  if (!response.ok) return [];
  try {
    return parseProviders(await response.json());
  } catch {
    return [];
  }
}

/**
 * The provider list, fetched at most once per page load.
 *
 * The list itself is memoised alongside the availability answer, so the login
 * page and the connected-accounts panel share one request. A fetch that
 * learned nothing is not cached, which is the `unknown` rule in
 * `availabilityCache`: the next ask tries again rather than showing no
 * providers for the life of the page over one dropped request.
 */
const lists = new Map<string, OAuthProvider[]>();

/** Drops the memoised lists. Tests only. */
export function resetProvidersForTests(): void {
  lists.clear();
}

export function oauthProviders(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<OAuthProvider[]> {
  return cachedAvailability(url, async () => {
    const providers = await fetchProviders(url, fetchImpl);
    if (providers.length === 0) {
      // Nothing to show, and nothing worth remembering: a backend that answered
      // an empty set and one that could not be reached are indistinguishable
      // here, and re-asking on the next mount is cheap.
      return 'unknown';
    }
    lists.set(url, providers);
    return 'available';
  }).then(() => lists.get(url) ?? []);
}
