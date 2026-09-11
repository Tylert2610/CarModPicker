/**
 * Reads `GET /api/auth/oauth/providers` to learn which OAuth providers this
 * deployment has configured, so the login page renders the real set. One
 * uncredentialed GET rather than a probe per provider.
 */
import { GITHUB_PROVIDER, GOOGLE_PROVIDER } from '@webbpulse/auth';

import { cachedAvailability } from './availabilityCache';

export { resetAvailabilityCache } from './availabilityCache';

/** Where the discovery route lives, relative to the identity origin. */
export const OAUTH_PROVIDERS_PATH = '/api/auth/oauth/providers';

/**
 * One provider the backend says is configured. `displayName` comes from the
 * server, which is the only thing that knows a provider this bundle predates.
 */
export interface OAuthProvider {
  id: string;
  displayName: string;
}

/**
 * A human name for a provider when the server sent none. Names the two baseline
 * providers and title cases anything else.
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
 * Parses the route body into a provider list, dropping any entry without a
 * usable `id` and falling back to {@link providerLabel} for a missing name.
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
 * Reads the discovery route uncredentialed. Every failure mode yields an empty
 * list, rendering no buttons, since a button that cannot work is worse.
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
 * The lists, keyed to match the shared availability cache so the login page and
 * the connected-accounts panel share one request.
 */
const lists = new Map<string, OAuthProvider[]>();

/** Drops the memoised lists. Tests only. */
export function resetProvidersForTests(): void {
  lists.clear();
}

/**
 * The configured providers, fetched at most once per page load. A fetch that
 * learned nothing is not cached, so the next ask tries again.
 */
export function oauthProviders(
  url: string,
  fetchImpl: typeof fetch = fetch
): Promise<OAuthProvider[]> {
  return cachedAvailability(url, async () => {
    const providers = await fetchProviders(url, fetchImpl);
    if (providers.length === 0) {
      return 'unknown';
    }
    lists.set(url, providers);
    return 'available';
  }).then(() => lists.get(url) ?? []);
}
