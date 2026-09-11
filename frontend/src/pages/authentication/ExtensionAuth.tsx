import { useEffect, useRef, useState } from 'react';
import {
  FaCheckCircle,
  FaExclamationTriangle,
  FaPuzzlePiece,
} from 'react-icons/fa';
import { Navigate, useSearchParams } from 'react-router-dom';
import { Alert, AlertDescription } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import { useAuth } from '../../hooks/useAuth';
import { getStoredToken } from '../../api/client';

type ExtensionRuntime = {
  sendMessage: (
    extensionId: string,
    message: unknown,
    callback?: (response: unknown) => void
  ) => void;
  lastError?: { message?: string };
};

type ExtensionChrome = {
  runtime?: ExtensionRuntime;
};

const getChromeRuntime = (): ExtensionRuntime | null => {
  const maybe = (window as unknown as { chrome?: ExtensionChrome }).chrome;
  return maybe?.runtime?.sendMessage ? maybe.runtime : null;
};

/**
 * Parse `VITE_ALLOWED_EXTENSION_IDS` into the set of extension ids this page
 * will hand a token to. Unknown ids are refused so a malicious site cannot
 * route visitors through `/extension-auth` with its own id.
 */
const getAllowedExtensionIds = (): ReadonlyArray<string> => {
  const raw = import.meta.env['VITE_ALLOWED_EXTENSION_IDS'] as
    string | undefined;
  if (!raw) return [];
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
};

const isExtensionIdAllowed = (extensionId: string): boolean => {
  const allowlist = getAllowedExtensionIds();
  if (allowlist.length > 0) return allowlist.includes(extensionId);
  return import.meta.env.DEV;
};

type HandoffState =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'success' }
  | { kind: 'error'; message: string };

/**
 * Legacy token handoff page for the Chrome extension, which passes a token to
 * an allowlisted extension id.
 */
function ExtensionAuth() {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();
  const [handoff, setHandoff] = useState<HandoffState>({ kind: 'idle' });
  const attemptedRef = useRef(false);

  const extensionId = searchParams.get('extensionId') ?? '';
  const state = searchParams.get('state') ?? '';

  useEffect(() => {
    if (attemptedRef.current) return;
    if (isLoading || !isAuthenticated) return;
    if (!extensionId || !state) {
      setHandoff({
        kind: 'error',
        message: 'Missing extensionId or state parameter.',
      });
      return;
    }
    if (!isExtensionIdAllowed(extensionId)) {
      setHandoff({
        kind: 'error',
        message:
          'This extension is not recognized. For your safety, sign-in was not completed.',
      });
      return;
    }
    const runtime = getChromeRuntime();
    if (!runtime) {
      setHandoff({
        kind: 'error',
        message:
          'Chrome extension APIs are not available. Make sure the CarModPicker extension is installed and this page is open in Chrome.',
      });
      return;
    }
    const token = getStoredToken();
    if (!token) {
      setHandoff({
        kind: 'error',
        message: 'No session token found. Please sign in and try again.',
      });
      return;
    }

    attemptedRef.current = true;
    setHandoff({ kind: 'sending' });
    runtime.sendMessage(
      extensionId,
      { type: 'carmodpicker-auth-handoff', token, state },
      (response: unknown) => {
        const lastErr = runtime.lastError;
        if (lastErr) {
          setHandoff({
            kind: 'error',
            message:
              lastErr.message ||
              'The extension did not respond. Is it installed and up to date?',
          });
          return;
        }
        const resp = response as
          { success?: boolean; error?: string } | undefined;
        if (resp?.success) {
          setHandoff({ kind: 'success' });
          window.setTimeout(() => {
            window.close();
          }, 1500);
        } else {
          setHandoff({
            kind: 'error',
            message: resp?.error || 'Sign-in handoff failed.',
          });
        }
      }
    );
  }, [isAuthenticated, isLoading, extensionId, state]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" text="Checking your session…" />
      </div>
    );
  }

  if (!isAuthenticated) {
    const current = `${window.location.pathname}${window.location.search}`;
    return (
      <Navigate to={`/login?returnTo=${encodeURIComponent(current)}`} replace />
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4">
      <div className="relative z-10 w-full max-w-md">
        <div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center shadow-lg">
                <FaPuzzlePiece className="text-primary-foreground text-2xl" />
              </div>
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">
              Connecting extension
            </h2>
          </div>

          {handoff.kind === 'sending' && (
            <div className="text-center">
              <Spinner size="md" text="Handing off your session…" />
            </div>
          )}

          {handoff.kind === 'success' && (
            <Alert variant="success" className="text-center">
              <FaCheckCircle className="!static text-3xl mx-auto mb-3" />
              <AlertDescription>
                <p className="font-medium mb-1">Extension signed in</p>
                <p className="text-muted-foreground text-sm">
                  You can close this tab and return to the extension.
                </p>
              </AlertDescription>
            </Alert>
          )}

          {handoff.kind === 'error' && (
            <Alert variant="destructive">
              <FaExclamationTriangle className="!top-5 !left-4 text-xl flex-shrink-0" />
              <AlertDescription>
                <p className="font-medium mb-1">
                  Sign-in couldn't be completed
                </p>
                <p className="text-sm opacity-80">{handoff.message}</p>
              </AlertDescription>
            </Alert>
          )}

          {handoff.kind === 'idle' && (
            <div className="text-center text-muted-foreground text-sm">
              Preparing…
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ExtensionAuth;
