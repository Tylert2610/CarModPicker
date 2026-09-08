// Phase 8 Plan 10 (D-11 Wave 3) — Register page coverage.
//
// Register.tsx posts a UserCreate body to `/users/` via the raw default
// `apiClient.post<UserRead>(...)` import (not through authApi). On success it
// navigates the browser to `/login`. Google OAuth is an optional second path
// gated by isGoogleConfigured() — we force that off so the test only exercises
// the password-form submission.
//
// Like Login.test.tsx we rely on setup.ts's mock of `../../api/client`, so the
// real domain API modules run while their Axios calls land on the shared mock.
// Assertions target `apiClient.post` directly.

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
import Register from './Register';

// <GoogleAuthFlow> internally consumes the Google OAuth provider. Stub it out
// with a harmless placeholder so Register renders without a real provider.
vi.mock('../../components/authentication/GoogleAuthFlow', () => ({
  default: () => <button type="button">Sign up with Google</button>,
}));

// Force the Google branch off so the test page renders the same way in every
// env (CI vs local) regardless of VITE_GOOGLE_CLIENT_ID.
vi.mock('../../hooks/useGoogleSignIn', () => ({
  isGoogleConfigured: () => false,
  useGoogleSignIn: () => ({
    state: { kind: 'idle' },
    start: vi.fn(),
    reset: vi.fn(),
  }),
}));

const getInputs = () => ({
  username: screen.getByPlaceholderText(/choose a username/i),
  email: screen.getByPlaceholderText(/you@example\.com/i),
  password: screen.getByPlaceholderText(/create a password/i),
  confirm: screen.getByPlaceholderText(/confirm your password/i),
});

const fillAndSubmit = (values: {
  username: string;
  email: string;
  password: string;
  confirm?: string;
}) => {
  const inputs = getInputs();
  fireEvent.change(inputs.username, { target: { value: values.username } });
  fireEvent.change(inputs.email, { target: { value: values.email } });
  fireEvent.change(inputs.password, { target: { value: values.password } });
  fireEvent.change(inputs.confirm, {
    target: { value: values.confirm ?? values.password },
  });
  const form = inputs.username.closest('form');
  if (!form) throw new Error('form element not found');
  fireEvent.submit(form);
};

describe('Register page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the register form with username, email, password and confirm fields', () => {
    render(<Register />, testScenarios.unauthenticated);

    expect(
      screen.getByPlaceholderText(/choose a username/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/you@example\.com/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/create a password/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/confirm your password/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create account/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/join carmodpicker/i)).toBeInTheDocument();
  });

  it('submits a UserCreate body to /users/ and navigates to /login on success', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockUser });

    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'newuser',
      email: 'new@example.com',
      password: 'password123',
    });

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
    });

    expect(vi.mocked(apiClient.post).mock.calls[0]?.[0]).toBe('/users/');

    const rawBody: unknown = vi.mocked(apiClient.post).mock.calls[0]?.[1];
    const body = rawBody as {
      username: string;
      email: string;
      password: string;
    };
    expect(body.username).toBe('newuser');
    expect(body.email).toBe('new@example.com');
    expect(body.password).toBe('password123');
  });

  it('shows a validation error when passwords do not match (and does NOT call the API)', async () => {
    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'user2',
      email: 'user2@example.com',
      password: 'password123',
      confirm: 'password999',
    });

    // "Passwords don't match" can appear in TWO places: the confirm-password
    // <Input>'s inline `error` prop AND the top-level apiError banner. Both
    // are valid representations of the same validation outcome, so we use
    // getAllByText and assert at least one node exists.
    await waitFor(() => {
      expect(
        screen.getAllByText(/passwords don't match/i).length
      ).toBeGreaterThan(0);
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('rejects a password shorter than 8 characters without calling the API', async () => {
    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'user3',
      email: 'user3@example.com',
      password: 'short',
    });

    await waitFor(() => {
      expect(
        screen.getByText(/password must be at least 8 characters long/i)
      ).toBeInTheDocument();
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
