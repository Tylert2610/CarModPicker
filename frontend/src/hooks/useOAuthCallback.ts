/**
 * Reads an OAuth callback out of the current URL, once per landing.
 *
 * ## What arrives here
 *
 * The backend owns the provider callback: it exchanges the code, sets the
 * refresh cookie, and then redirects the browser back to a frontend page with
 * exactly one marker in the query string.
 *
 *   - `?oauth=1`          a completed sign in
 *   - `?mfa_ticket=...`   the provider proved identity, a second factor is owed
 *   - `?oauth_linked=1`   a provider was attached to the signed in account
 *   - `?oauth_error=CODE` a refusal, or a consent screen the user cancelled
 *
 * `readOAuthCallback` in the package parses all four and returns `null` for a
 * page that was not reached from a callback, which is every direct visit.
 *
 * ## Why the parameters are stripped
 *
 * They are single use and the page is bookmarkable. Leaving `?oauth=1` in the
 * URL means a reload re-runs the effect and a shared link carries a marker that
 * means nothing to whoever opens it. `stripOAuthParams` removes exactly the
 * parameters the standard owns and leaves the page's own query alone, and it is
 * done with `history.replaceState` so the back button still goes back where the
 * user expects rather than to the callback.
 *
 * ## Why a ref rather than an empty dependency array
 *
 * React 18 and later mount effects twice in development's strict mode. The
 * parameters are single use, so the second run would read a URL the first run
 * already cleared and conclude nothing happened. The ref makes the read happen
 * exactly once per page load regardless.
 */
import { useEffect, useRef } from 'react';
import {
  readOAuthCallback,
  stripOAuthParams,
  type OAuthCallbackResult,
} from '../api/identityOAuth';
import { AUTH_MODE } from '../api/authMode';

/** What the caller is told, once, when the page was reached from a callback. */
export type OAuthCallbackHandler = (
  result: OAuthCallbackResult
) => void | Promise<void>;

/**
 * Runs `onCallback` when the page was reached from an OAuth callback.
 *
 * A no-op in bearer mode, where nothing produces these markers, and a no-op on
 * every ordinary visit.
 */
export function useOAuthCallback(onCallback: OAuthCallbackHandler): void {
  const handled = useRef(false);
  const handler = useRef(onCallback);
  handler.current = onCallback;

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;
    if (AUTH_MODE !== 'identity') return;
    const href = globalThis.location.href;
    const result = readOAuthCallback(href);
    if (result === null) return;
    globalThis.history.replaceState(null, '', stripOAuthParams(href));
    void handler.current(result);
  }, []);
}

export default useOAuthCallback;
