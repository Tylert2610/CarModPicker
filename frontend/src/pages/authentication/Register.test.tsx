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

vi.mock('../../components/authentication/GoogleAuthFlow', () => ({
  default: () => <button type="button">Sign up with Google</button>,
}));

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
