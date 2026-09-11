/**
 * Reads an OAuth callback marker out of the current URL once per landing, then
 * strips the single-use parameters so a reload or shared link cannot replay
 * them. A ref guards the read, since strict mode mounts effects twice.
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
