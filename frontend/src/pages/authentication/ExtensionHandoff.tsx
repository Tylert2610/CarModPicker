/**
 * Web sign in handoff for the Chrome extension in identity mode.
 *
 * The refresh token stays an httpOnly cookie on this origin; only a single use
 * code crosses to the extension, in the fragment, after the redirect target is
 * validated against the allowlist so this page cannot become an open redirect.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FaCheckCircle,
  FaExclamationTriangle,
  FaPuzzlePiece,
} from 'react-icons/fa';
import { Navigate, useSearchParams } from 'react-router-dom';
import { Alert, AlertDescription } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import { useAuth } from '../../hooks/useAuth';
import { AUTH_MODE } from '../../api/authMode';
import { getIdentityClient, identityUrl } from '../../api/identityClient';

/** Backend route that exchanges a validated handoff for a code. */
export const EXTENSION_HANDOFF_PATH = '/api/auth/extension/handoff';

/**
 * Extension ids this frontend will hand a code to, from
 * `VITE_ALLOWED_EXTENSION_IDS`. Empty means no extension is trusted.
 */
export const allowedExtensionIds = (
  env: Record<string, unknown> = import.meta.env
): string[] => {
  const raw = env['VITE_ALLOWED_EXTENSION_IDS'];
  if (typeof raw !== 'string') return [];
  return raw
    .split(',')
    .map((id) => id.trim())
    .filter((id) => id !== '');
};

/**
 * The validated redirect target, or null when it is not one this page will use.
 * Checks the `chrome-extension:` scheme and allowlist membership of the id.
 */
export const validateRedirectUri = (
  value: string | null,
  allowed: readonly string[]
): string | null => {
  if (value === null || value === '') return null;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (url.protocol !== 'chrome-extension:') return null;
  if (url.hostname === '' || !allowed.includes(url.hostname)) return null;
  return url.toString();
};

type State =
  | { kind: 'working' }
  | { kind: 'refused'; message: string }
  | { kind: 'coming-soon' }
  | { kind: 'handing-off' };

/**
 * Signs the user in, validates the extension redirect target, and hands back a
 * single use code in the URL fragment.
 */
function ExtensionHandoff() {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  const [state, setState] = useState<State>({ kind: 'working' });
  const attempted = useRef(false);

  const redirectUri = searchParams.get('redirect_uri');
  const extensionState = searchParams.get('state') ?? '';

  const run = useCallback(async () => {
    if (AUTH_MODE !== 'identity') {
      setState({
        kind: 'refused',
        message:
          'This deployment does not use the shared sign in service, so there is nothing to hand off.',
      });
      return;
    }
    const target = validateRedirectUri(redirectUri, allowedExtensionIds());
    if (target === null) {
      setState({
        kind: 'refused',
        message:
          'That extension is not recognised. For your safety, nothing was handed over.',
      });
      return;
    }
    const identity = getIdentityClient();
    if (identity === null) {
      setState({
        kind: 'refused',
        message: 'Sign in is not available in this deployment.',
      });
      return;
    }

    let response: Response;
    try {
      response = await fetch(identityUrl(EXTENSION_HANDOFF_PATH), {
        method: 'POST',
        credentials: 'include',
        headers: {
          accept: 'application/json',
          'content-type': 'application/json',
          authorization: `Bearer ${identity.getAccessToken() ?? ''}`,
        },
        body: JSON.stringify({ redirect_uri: target, state: extensionState }),
      });
    } catch {
      setState({
        kind: 'refused',
        message: 'Could not reach the sign in service. Please try again.',
      });
      return;
    }

    if (response.status === 404) {
      setState({ kind: 'coming-soon' });
      return;
    }
    if (!response.ok) {
      setState({
        kind: 'refused',
        message: 'The sign in service refused the handoff.',
      });
      return;
    }

    let code: unknown;
    try {
      code = ((await response.json()) as { code?: unknown }).code;
    } catch {
      code = undefined;
    }
    if (typeof code !== 'string' || code === '') {
      setState({
        kind: 'refused',
        message: 'The sign in service did not return a handoff code.',
      });
      return;
    }

    const fragment = new URLSearchParams({ code });
    if (extensionState !== '') fragment.set('state', extensionState);
    setState({ kind: 'handing-off' });
    globalThis.location.replace(`${target}#${fragment.toString()}`);
  }, [redirectUri, extensionState]);

  useEffect(() => {
    if (attempted.current) return;
    if (isLoading || !isAuthenticated) return;
    attempted.current = true;
    void run();
  }, [isLoading, isAuthenticated, run]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!isAuthenticated) {
    const returnTo = `${globalThis.location.pathname}${globalThis.location.search}`;
    return (
      <Navigate
        to={`/login?returnTo=${encodeURIComponent(returnTo)}`}
        replace
      />
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-8 text-center">
        <div className="mb-4 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary">
            <FaPuzzlePiece className="text-2xl text-primary-foreground" />
          </div>
        </div>
        <h1 className="mb-2 text-2xl font-bold text-white">
          Connect the CarModPicker extension
        </h1>

        {state.kind === 'working' && (
          <div className="flex flex-col items-center gap-3">
            <Spinner />
            <p className="text-muted-foreground">Completing sign in…</p>
          </div>
        )}

        {state.kind === 'handing-off' && (
          <div className="flex flex-col items-center gap-3">
            <FaCheckCircle className="text-3xl text-green-400" />
            <p className="text-muted-foreground">
              Signed in. Returning to the extension…
            </p>
          </div>
        )}

        {state.kind === 'coming-soon' && (
          <Alert>
            <AlertDescription>
              Signing the extension in from the web is not switched on in this
              deployment yet. You are signed in here, and the extension will be
              able to use it as soon as the service supports the handoff.
            </AlertDescription>
          </Alert>
        )}

        {state.kind === 'refused' && (
          <Alert variant="destructive">
            <AlertDescription>
              <span className="mr-2 inline-block align-middle">
                <FaExclamationTriangle />
              </span>
              {state.message}
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}

export default ExtensionHandoff;
