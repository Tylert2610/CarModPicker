// Phase 8 Plan 10 (D-11 Wave 3) — Login page coverage.
//
// Login.tsx wires together three sign-in surfaces: the password form (posts to
// /auth/token via authApi.login), a passkey (WebAuthn) button, and the Google
// OAuth button rendered via <GoogleAuthFlow>. Per PATTERNS.md §11 + the plan's
// interfaces block we exercise ONLY the password-form happy path and its
// error branch; OAuth + WebAuthn are mocked at the module level so the UI
// renders but their flows are not invoked (D-11 "happy-path + one error", not
// OAuth flow).
//
// Mocking: setup.ts mocks `../api/client`, so when Login.tsx calls
// authApi.login(...), the real authApi code runs and internally hits
// `apiClient.post(...)` which lands on the mocked client. We therefore assert
// on `apiClient.post`, not on authApi.
//
// We use `fireEvent` (not userEvent) for form submission — jsdom +
// `userEvent.click` on a submit button inside nested containers is flaky
// under Vitest's test isolation, but `fireEvent.submit(form)` is
// deterministic.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import { mockUser } from '../../test/mocks/api';
import Login from './Login';

// Mock WebAuthn browser module so passkey feature detection is deterministic
// and we don't accidentally invoke navigator.credentials during tests.
vi.mock('@simplewebauthn/browser', () => ({
  startAuthentication: vi.fn(),
  browserSupportsWebAuthn: vi.fn(() => false),
}));

// <GoogleAuthFlow> internally consumes the useGoogleSignIn hook and renders a
// <GoogleLogin> from @react-oauth/google. Stub the whole component to a
// predictable button so the Login page renders without needing a real
// GoogleOAuthProvider in the test tree.
vi.mock('../../components/authentication/GoogleAuthFlow', () => ({
  default: () => <button type="button">Sign in with Google</button>,
}));

// isGoogleConfigured reads VITE_GOOGLE_CLIENT_ID. Force "disabled" so the
// Google button branch only renders through the GoogleAuthFlow stub above
// (when WebAuthn is also off, the entire OAuth/WebAuthn block is skipped).
vi.mock('../../hooks/useGoogleSignIn', () => ({
  isGoogleConfigured: () => false,
  useGoogleSignIn: () => ({
    state: { kind: 'idle' },
    start: vi.fn(),
    reset: vi.fn(),
  }),
}));

const fillAndSubmit = (username: string, password: string) => {
  const usernameInput = screen.getByPlaceholderText(/enter your username/i);
  const passwordInput = screen.getByPlaceholderText(/enter your password/i);
  fireEvent.change(usernameInput, { target: { value: username } });
  fireEvent.change(passwordInput, { target: { value: password } });
  const form = usernameInput.closest('form');
  if (!form) throw new Error('form element not found');
  fireEvent.submit(form);
};

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the login form with username, password and submit controls', () => {
    render(<Login />, testScenarios.unauthenticated);

    // htmlFor is not wired on Login's <Input>s (no `id` prop passed), so we
    // locate inputs by placeholder/role instead of getByLabelText.
    expect(
      screen.getByPlaceholderText(/enter your username/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/enter your password/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /sign in/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /forgot your password/i })
    ).toBeInTheDocument();
  });

  it('submits credentials and calls apiClient.post on /auth/token', async () => {
    // authApi.login POSTs to /auth/token with x-www-form-urlencoded. The real
    // authApi runs (setup.ts preserves it via importOriginal) and hits the
    // mocked apiClient.post under the hood.
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        access_token: 'tok',
        token_type: 'bearer',
        user: mockUser,
        requires_2fa: false,
      },
    });

    render(<Login />, testScenarios.unauthenticated);
    fillAndSubmit('testuser', 'password');

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
    });
    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe('/auth/token');

    const rawBody: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[1];
    expect(rawBody).toBeInstanceOf(URLSearchParams);
    const body = rawBody as URLSearchParams;
    expect(body.get('username')).toBe('testuser');
    expect(body.get('password')).toBe('password');

    const rawConfig: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[2];
    const config = rawConfig as { headers?: Record<string, string> };
    expect(config.headers?.['Content-Type']).toBe(
      'application/x-www-form-urlencoded'
    );
  });

  it('surfaces an error message when credentials are invalid (401)', async () => {
    // parseApiError in useApiRequest reads `message` off the error envelope
    // in response.data.
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 401,
        data: {
          success: false,
          status: 401,
          message: 'Invalid credentials',
          request_id: 'req-1',
          error_code: 'UNAUTHORIZED',
        },
      },
    });

    render(<Login />, testScenarios.unauthenticated);
    fillAndSubmit('baduser', 'badpass');

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
    expect(apiClient.post).toHaveBeenCalledTimes(1);
  });

  it('validates empty form before calling the API', async () => {
    render(<Login />, testScenarios.unauthenticated);

    // Whitespace-only values bypass the browser's `required` check but trip
    // the component's own trim() guard, surfacing the validation message.
    fillAndSubmit('   ', '   ');

    await waitFor(() => {
      expect(
        screen.getByText(/username and password cannot be empty/i)
      ).toBeInTheDocument();
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
