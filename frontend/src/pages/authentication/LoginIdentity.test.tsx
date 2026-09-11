import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const navigate = vi.fn();
const authLogin = vi.fn();
const checkAuthStatus = vi.fn().mockResolvedValue(undefined);

/** Whatever the passkey availability route should answer for one test. */
let passkeyAnswer: 'available' | 'unavailable' | 'unknown' = 'unavailable';
/** Whatever the discovery route should answer for one test. */
let providerList: { id: string; displayName: string }[] = [];
/** Whatever a passkey sign in should produce for one test. */
let passkeyResult: unknown = { status: 'cancelled' };
/** Whatever the password first leg should produce for one test. */
let signInResult: unknown = { status: 'failed', error: 'nope' };
/** Whatever the second leg should produce for one test. */
let mfaResult: unknown = { status: 'authenticated', user: null };

/**
 * `passkeyResult` is what a pressed sign in produces. The conditional request
 * armed on mount is left hanging, as a real one is when no discoverable
 * credential exists; a test wanting that path sets `conditionalResult`.
 */
let conditionalResult: unknown = undefined;

const signInWithPasskey = vi.fn((options?: { mediation?: string }) => {
  if (options?.mediation === 'conditional') {
    return conditionalResult === undefined
      ? new Promise(() => {})
      : Promise.resolve(conditionalResult);
  }
  return Promise.resolve(passkeyResult);
});
const signIn = vi.fn(() => Promise.resolve(signInResult));
const completeMfa = vi.fn(() => Promise.resolve(mfaResult));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigate };
});

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    login: authLogin,
    checkAuthStatus,
    isAuthenticated: false,
    isLoading: false,
    user: null,
  }),
}));

vi.mock('../../api/authMode', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/authMode')>();
  return { ...actual, AUTH_MODE: 'identity' as const };
});

vi.mock('../../api/identityAuth', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/identityAuth')>();
  return {
    ...actual,
    signIn: (...args: unknown[]) => signIn(...(args as [])),
    completeMfa: (...args: unknown[]) => completeMfa(...(args as [])),
    acceptsRecoveryCodes: () => true,
  };
});

vi.mock('../../api/identityPasskeys', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/identityPasskeys')>();
  return {
    ...actual,
    passkeysSupported: () => true,
    signInWithPasskey: (options?: { mediation?: string }) =>
      signInWithPasskey(options),
  };
});

vi.mock('../../api/passkeyAvailability', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/passkeyAvailability')>();
  return {
    ...actual,
    passkeyLoginAvailability: () => Promise.resolve(passkeyAnswer),
  };
});

vi.mock('../../api/oauthProviders', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/oauthProviders')>();
  return { ...actual, oauthProviders: () => Promise.resolve(providerList) };
});

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () => ({ oauthStartUrl: () => 'https://api.test/start' }),
  identityUrl: (path: string) => `https://api.test${path}`,
}));

vi.mock('../../api/identityOAuth', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/identityOAuth')>();
  return {
    ...actual,
    oauthStartUrl: (provider: string) =>
      `https://api.test/api/auth/oauth/${provider}/start`,
  };
});

vi.mock('@simplewebauthn/browser', () => ({
  startAuthentication: vi.fn(),
  browserSupportsWebAuthn: () => false,
}));
vi.mock('../../components/authentication/GoogleAuthFlow', () => ({
  default: () => null,
}));
vi.mock('../../hooks/useGoogleSignIn', () => ({
  isGoogleConfigured: () => false,
  useGoogleSignIn: () => ({ state: { kind: 'idle' }, reset: vi.fn() }),
}));

const renderLogin = async () => {
  const { default: Login } = await import('./Login');
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
};

const setUrl = (search: string) => {
  globalThis.history.replaceState(null, '', `/login${search}`);
};

beforeEach(() => {
  vi.clearAllMocks();
  passkeyAnswer = 'unavailable';
  providerList = [];
  passkeyResult = { status: 'cancelled' };
  conditionalResult = undefined;
  signInResult = { status: 'failed', error: 'nope' };
  mfaResult = { status: 'authenticated', user: null };
  setUrl('');
});

afterEach(() => {
  setUrl('');
});

describe('the passkey button', () => {
  it('is absent while the read is in flight and when it says unavailable', async () => {
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in$/i })).toBeTruthy();
    });
    expect(screen.queryByText(/sign in with a passkey/i)).toBeNull();
  });

  it('appears when the deployment has passwordless sign in on', async () => {
    passkeyAnswer = 'available';
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByText(/sign in with a passkey/i)).toBeTruthy();
    });
  });

  it('stays hidden when the read learned nothing', async () => {
    passkeyAnswer = 'unknown';
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in$/i })).toBeTruthy();
    });
    expect(screen.queryByText(/sign in with a passkey/i)).toBeNull();
  });

  it('arms conditional mediation on mount', async () => {
    passkeyAnswer = 'available';
    await renderLogin();
    await waitFor(() => {
      expect(signInWithPasskey).toHaveBeenCalledWith(
        expect.objectContaining({ mediation: 'conditional' })
      );
    });
  });

  it('signs in from the autofill chooser, with no press at all', async () => {
    passkeyAnswer = 'available';
    conditionalResult = { status: 'authenticated' };
    await renderLogin();
    await waitFor(() => {
      expect(checkAuthStatus).toHaveBeenCalled();
    });
  });

  it('ignores a cancelled conditional request', async () => {
    passkeyAnswer = 'available';
    conditionalResult = { status: 'cancelled' };
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByText(/sign in with a passkey/i)).toBeTruthy();
    });
    expect(checkAuthStatus).not.toHaveBeenCalled();
  });

  it('signs in when the ceremony succeeds', async () => {
    passkeyAnswer = 'available';
    passkeyResult = { status: 'authenticated' };
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByText(/sign in with a passkey/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByText(/sign in with a passkey/i));
    await waitFor(() => {
      expect(checkAuthStatus).toHaveBeenCalled();
    });
  });

  it('moves to the code step when the account still owes a second factor', async () => {
    passkeyAnswer = 'available';
    passkeyResult = {
      status: 'mfa-required',
      ticket: 'tick-1',
      factors: ['totp'],
    };
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByText(/sign in with a passkey/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByText(/sign in with a passkey/i));
    await waitFor(() => {
      expect(screen.getByText(/two-factor authentication/i)).toBeTruthy();
    });
  });
});

describe('the provider buttons', () => {
  it('render nothing when the deployment has no provider configured', async () => {
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in$/i })).toBeTruthy();
    });
    expect(screen.queryByText(/continue with/i)).toBeNull();
  });

  it('render one button per configured provider, with the server name', async () => {
    providerList = [
      { id: 'google', displayName: 'Google' },
      { id: 'okta', displayName: 'Acme SSO' },
    ];
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByText(/continue with google/i)).toBeTruthy();
    });
    expect(screen.getByText(/continue with acme sso/i)).toBeTruthy();
  });

  it('render as links, because the start route answers a redirect', async () => {
    providerList = [{ id: 'google', displayName: 'Google' }];
    await renderLogin();
    const link = await screen.findByText(/continue with google/i);
    const anchor = link.closest('a');
    expect(anchor).toBeTruthy();
    expect(anchor?.getAttribute('href')).toContain(
      '/api/auth/oauth/google/start'
    );
  });
});

describe('the TOTP step', () => {
  it('appears after the first leg and completes on a code', async () => {
    signInResult = {
      status: 'mfa-required',
      challenge: { kind: 'identity-ticket', ticket: 'tick-1', factors: [] },
    };
    await renderLogin();
    fireEvent.change(screen.getByPlaceholderText(/enter your username/i), {
      target: { value: 'me' },
    });
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'pw' },
    });
    fireEvent.submit(
      screen.getByPlaceholderText(/enter your username/i).closest('form')!
    );

    await waitFor(() => {
      expect(screen.getByText(/two-factor authentication/i)).toBeTruthy();
    });

    const code = screen.getByLabelText(/authentication code/i);
    fireEvent.change(code, { target: { value: '123456' } });
    fireEvent.submit(code.closest('form')!);

    await waitFor(() => {
      expect(completeMfa).toHaveBeenCalledWith(
        { kind: 'identity-ticket', ticket: 'tick-1', factors: [] },
        '123456'
      );
    });
  });

  it('accepts a recovery code, which is not six digits', async () => {
    signInResult = {
      status: 'mfa-required',
      challenge: { kind: 'identity-ticket', ticket: 'tick-1', factors: [] },
    };
    await renderLogin();
    fireEvent.change(screen.getByPlaceholderText(/enter your username/i), {
      target: { value: 'me' },
    });
    fireEvent.change(screen.getByPlaceholderText(/enter your password/i), {
      target: { value: 'pw' },
    });
    fireEvent.submit(
      screen.getByPlaceholderText(/enter your username/i).closest('form')!
    );
    await waitFor(() => {
      expect(screen.getByText(/two-factor authentication/i)).toBeTruthy();
    });

    const code = screen.getByLabelText(/authentication code/i);
    fireEvent.change(code, { target: { value: 'abcd-efgh-ijkl' } });
    expect((code as HTMLInputElement).value).toBe('abcd-efgh-ijkl');
  });
});

describe('the OAuth callback', () => {
  it('finishes a sign in on ?oauth=1', async () => {
    setUrl('?oauth=1');
    await renderLogin();
    await waitFor(() => {
      expect(checkAuthStatus).toHaveBeenCalled();
    });
    expect(globalThis.location.search).not.toContain('oauth=1');
  });

  it('moves to the code step on ?mfa_ticket=', async () => {
    setUrl('?mfa_ticket=tick-9');
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByText(/two-factor authentication/i)).toBeTruthy();
    });
  });

  it('shows a message on ?oauth_error=', async () => {
    setUrl('?oauth_error=OAUTH_ACCOUNT_MISMATCH');
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });

  it('does nothing on an ordinary visit', async () => {
    await renderLogin();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in$/i })).toBeTruthy();
    });
    expect(checkAuthStatus).not.toHaveBeenCalled();
  });
});
