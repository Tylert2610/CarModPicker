/**
 * Tests for Sentry initialization and its environment gate.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Covers Sentry initialisation, its options, and the replay sampling gate.
 * Imports dynamically after `vi.stubEnv` so the module re-reads env at load.
 */

const mockedInit = vi.fn();
const mockedBrowserTracing = vi.fn(() => ({ name: 'browserTracing' }));
const mockedReplay = vi.fn((opts: unknown) => ({
  name: 'replay',
  _opts: opts,
}));
const mockedCaptureException = vi.fn();
const mockedSetUser = vi.fn();

vi.mock('@sentry/react', () => ({
  init: mockedInit,
  browserTracingIntegration: mockedBrowserTracing,
  replayIntegration: mockedReplay,
  captureException: mockedCaptureException,
  setUser: mockedSetUser,
}));

type SentryInitConfig = {
  sendDefaultPii?: boolean;
  replaysSessionSampleRate?: number;
  replaysOnErrorSampleRate?: number;
  tracesSampleRate?: number;
  environment?: string;
  dsn?: string;
  release?: string;
};

type ReplayOpts = {
  beforeErrorSampling: () => boolean;
  maskAllText?: boolean;
  maskAllInputs?: boolean;
};

describe('initSentry — env gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it('no-ops when MODE is development', async () => {
    vi.stubEnv('MODE', 'development');
    vi.stubEnv('VITE_SENTRY_DSN', 'https://x@y/1');
    const { initSentry } = await import('./sentry');
    initSentry();
    expect(mockedInit).not.toHaveBeenCalled();
  });

  it('no-ops when DSN is empty', async () => {
    vi.stubEnv('MODE', 'production');
    vi.stubEnv('VITE_SENTRY_DSN', '');
    const { initSentry } = await import('./sentry');
    initSentry();
    expect(mockedInit).not.toHaveBeenCalled();
  });

  it('initializes in staging with DSN', async () => {
    vi.stubEnv('MODE', 'staging');
    vi.stubEnv('VITE_SENTRY_DSN', 'https://x@y/1');
    const { initSentry } = await import('./sentry');
    initSentry();
    expect(mockedInit).toHaveBeenCalledTimes(1);
  });
});

describe('initSentry — config invariants', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv('MODE', 'production');
    vi.stubEnv('VITE_SENTRY_DSN', 'https://x@y/1');
  });

  it('sets sendDefaultPii false, replay sample rates, traces sample rate', async () => {
    const { initSentry } = await import('./sentry');
    initSentry();
    const cfg = mockedInit.mock.calls[0]?.[0] as SentryInitConfig;
    expect(cfg.sendDefaultPii).toBe(false);
    expect(cfg.replaysSessionSampleRate).toBe(0);
    expect(cfg.replaysOnErrorSampleRate).toBe(1.0);
    expect(cfg.tracesSampleRate).toBe(0.05);
  });

  it('passes environment = MODE', async () => {
    const { initSentry } = await import('./sentry');
    initSentry();
    const cfg = mockedInit.mock.calls[0]?.[0] as SentryInitConfig;
    expect(cfg.environment).toBe('production');
  });

  it('passes dsn and release from env', async () => {
    vi.stubEnv('VITE_SENTRY_RELEASE', 'frontend@1.2.3');
    const { initSentry } = await import('./sentry');
    initSentry();
    const cfg = mockedInit.mock.calls[0]?.[0] as SentryInitConfig;
    expect(cfg.dsn).toBe('https://x@y/1');
    expect(cfg.release).toBe('frontend@1.2.3');
  });

  it('configures Session Replay masks (maskAllText + maskAllInputs)', async () => {
    const { initSentry } = await import('./sentry');
    initSentry();
    const replayOpts = mockedReplay.mock.calls[0]?.[0] as ReplayOpts;
    expect(replayOpts.maskAllText).toBe(true);
    expect(replayOpts.maskAllInputs).toBe(true);
  });
});

describe('beforeErrorSampling auth-route gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv('MODE', 'production');
    vi.stubEnv('VITE_SENTRY_DSN', 'https://x@y/1');
  });

  async function extractHook(): Promise<() => boolean> {
    const { initSentry } = await import('./sentry');
    initSentry();
    const replayCall = mockedReplay.mock.calls[0]?.[0] as ReplayOpts;
    return replayCall.beforeErrorSampling;
  }

  function setPath(p: string) {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...window.location, pathname: p },
    });
  }

  it.each([
    '/login',
    '/register',
    '/oauth-callback',
    '/reset-password',
    '/2fa',
  ])('drops replay on auth path %s', async (path: string) => {
    const hook = await extractHook();
    setPath(path);
    expect(hook()).toBe(false);
  });

  it.each(['/login/extra', '/register/foo', '/oauth-callback/redirect'])(
    'drops replay on auth-path prefix match %s',
    async (path: string) => {
      const hook = await extractHook();
      setPath(path);
      expect(hook()).toBe(false);
    }
  );

  it.each(['/dashboard', '/cars', '/', '/build-lists/42'])(
    'attaches replay on non-auth path %s',
    async (path: string) => {
      const hook = await extractHook();
      setPath(path);
      expect(hook()).toBe(true);
    }
  );
});
