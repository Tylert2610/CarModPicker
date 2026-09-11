/**
 * OAuth sign in and account link operations in identity mode. A start must be a
 * real navigation rather than a fetch, since it redirects cross-origin to the
 * provider; the backend callback returns with a marker query parameter.
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
  { status: 'ok' } | { status: 'failed'; error: string };

/** The sentence shown when the identity client is not the running mechanism. */
const UNAVAILABLE = 'Connected accounts are not available in this deployment.';

/**
 * The URL a "Continue with X" button points at, or null in bearer mode.
 * `returnTo` is a path the server resolves against its own frontend base.
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
 * Starts attaching a provider to the signed in account, navigating for the same
 * reason a sign in start does. A refusal carries the server's wording.
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
        error instanceof Error
          ? error.message
          : 'Could not connect that account.',
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
 * Detaches a provider from the signed in account. Refused when it is the last
 * way in, carrying the server's own explanation of what to do first.
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
