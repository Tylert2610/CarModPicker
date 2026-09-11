import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import { buildApiError } from '../../test/apiResponse';
import { mockUser } from '../../test/mocks/api';
import Login from './Login';

vi.mock('@simplewebauthn/browser', () => ({
  startAuthentication: vi.fn(),
  browserSupportsWebAuthn: vi.fn(() => false),
}));

vi.mock('../../components/authentication/GoogleAuthFlow', () => ({
  default: () => <button type="button">Sign in with Google</button>,
}));

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
    const body =
      rawBody instanceof URLSearchParams
        ? {
            username: rawBody.get('username'),
            password: rawBody.get('password'),
          }
        : (rawBody as { username: string; password: string });
    expect(body.username).toBe('testuser');
    expect(body.password).toBe('password');

    const rawConfig: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[2];
    const config = rawConfig as { headers?: Record<string, string> };
    expect(config.headers?.['Content-Type']).toBe(
      'application/x-www-form-urlencoded'
    );
  });

  it('surfaces an error message when credentials are invalid (401)', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(
      buildApiError(401, {
        success: false,
        status: 401,
        message: 'Invalid credentials',
        request_id: 'req-1',
        error_code: 'UNAUTHORIZED',
      })
    );

    render(<Login />, testScenarios.unauthenticated);
    fillAndSubmit('baduser', 'badpass');

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
    expect(apiClient.post).toHaveBeenCalledTimes(1);
  });

  it('validates empty form before calling the API', async () => {
    render(<Login />, testScenarios.unauthenticated);

    fillAndSubmit('   ', '   ');

    await waitFor(() => {
      expect(
        screen.getByText(/username and password cannot be empty/i)
      ).toBeInTheDocument();
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
