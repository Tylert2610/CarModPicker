/**
 * Sentry initialization and the helpers that report errors from the app.
 */

import * as Sentry from '@sentry/react';

/**
 * Initialises Sentry outside development. Session Replay attaches on error
 * only, and no personally identifying data is sent: IP is excluded, text and
 * inputs are masked, and only a user id is ever set.
 */

/**
 * Pathname prefixes where Session Replay must not attach, since these URLs can
 * carry tokens. Errors on these pages still report; only the replay is dropped.
 */
const AUTH_PATHS = [
  '/login',
  '/register',
  '/oauth-callback',
  '/reset-password',
  '/2fa',
];

/** Starts Sentry when a DSN is configured, and does nothing when it is not. */
export function initSentry(): void {
  if (import.meta.env.MODE === 'development') return;

  const dsn = import.meta.env['VITE_SENTRY_DSN'] as string | undefined;
  if (!dsn) return;

  const release = import.meta.env['VITE_SENTRY_RELEASE'] as string | undefined;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    release,
    sendDefaultPii: false,
    tracesSampleRate: 0.05,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: true,
        maskAllInputs: true,
        blockAllMedia: true,
        beforeErrorSampling: () => {
          const path = window.location.pathname;
          return !AUTH_PATHS.some((p) => path.startsWith(p));
        },
      }),
    ],
  });
}
