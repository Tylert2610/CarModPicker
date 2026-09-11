/**
 * The OAuth operations in identity mode: starting a sign in, and managing the
 * links on a signed in account.
 *
 * ## Why starting is a navigation and not a fetch
 *
 * `POST /api/auth/oauth/<provider>/start` answers a `302` to the provider's
 * authorization endpoint, which is a cross-origin redirect to a host that sends
 * no CORS headers. A `fetch` would chase it and reject on the CORS failure at
 * the *provider*, so a start has to be a real navigation. `AuthClient` exposes
 * both halves of that: `oauthStartUrl` builds the URL and `startOAuth` builds
 * it and navigates. The buttons render as anchors carrying the URL, which also
 * gets middle-click and "open in new tab" for free.
 *
 * ## What comes back
 *
 * The provider returns to its callback on the backend, which finishes the
 * exchange and redirects to the frontend with exactly one of four markers:
 * `?oauth=1` for a completed sign in, `?mfa_ticket=` when a second factor is
 * still owed, `?oauth_linked=1` when a link was attached, and
 * `?oauth_error=CODE` for a refusal. `readOAuthCallback` in the package parses
 * all four, and `./oauthCallback` is the hook that acts on the result and
 * strips the parameters back off the URL.
 */
import {
  describeOAuthCallbackError,
  readOAuthCallback,
  stripOAuthParams,
  type OAuthCallbackResult,
  type OAuthLink,
} from '@webbpulse/auth';
import { getIdentityClient } from './identityClient';

export { describeOAuthCallbackError, readOAuthCallback, stripOAuthParams };
export type { OAuthCallbackResult, OAuthLink };

/** What a link or unlink produced, in the one shape the panel renders. */
export type OAuthLinkResult =
  | { status: 'ok' }
  | { status: 'failed'; error: string };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Connected accounts are not available in this deployment.';

/**
 * The URL a "Continue with X" button points at, or null when there is no
 * identity client to build one.
 *
 * `returnTo` is where the frontend lands after the callback, and it is a path
 * rather than an absolute URL: the server resolves it against its own
 * configured frontend base, and a `returnTo` it cannot match falls back to the
 * root rather than being refused.
 */
export const oauthStartUrl = (
  provider: string,
  returnTo?: string
): string | null => {
  const identity = getIdentityClient();
  if (identity === null) return null;
  return identity.oauthStartUrl(provider, {
    mode: 'login',
    ...(returnTo === undefined ? {} : { returnTo }),
  });
};

/**
 * Starts attaching a provider to the signed in account.
 *
 * A link start is a navigation for the same reason a sign in start is, and the
 * package's `linkOAuthProvider` performs it. A refusal here is usually
 * `OAUTH_ALREADY_LINKED`, which the server words better than this module could.
 */
export const linkProvider = async (
  provider: string,
  returnTo?: string
): Promise<OAuthLinkResult> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.linkOAuthProvider(provider, {
      ...(returnTo === undefined ? {} : { returnTo }),
    });
    return outcome.ok
      ? { status: 'ok' }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error ? error.message : 'Could not connect that account.',
    };
  }
};

/** The providers attached to the signed in account. */
export const listLinks = async (): Promise<
  { status: 'ok'; links: OAuthLink[] } | { status: 'failed'; error: string }
> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.listOAuthLinks();
    return outcome.ok
      ? { status: 'ok', links: outcome.links }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not load your connected accounts.',
    };
  }
};

/**
 * Detaches a provider from the signed in account.
 *
 * Refused when it is the last way into the account, which the package models as
 * `OAuthLastSignInMethod`. Like the passkey last-credential rule, that is a
 * refusal with a concrete next step rather than an error, and the server's own
 * sentence is the one that explains it.
 */
export const unlinkProvider = async (
  provider: string
): Promise<OAuthLinkResult> => {
  const identity = getIdentityClient();
  if (identity === null) return { status: 'failed', error: UNAVAILABLE };
  try {
    const outcome = await identity.unlinkOAuthProvider(provider);
    return outcome.ok
      ? { status: 'ok' }
      : { status: 'failed', error: outcome.message };
  } catch (error) {
    return {
      status: 'failed',
      error:
        error instanceof Error
          ? error.message
          : 'Could not disconnect that account.',
    };
  }
};
