import { describe, it, expect } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { render, screen } from '../../test/utils/test-utils';
import VerifyEmailRoute from './VerifyEmailRoute';

/** Mounts the guard over a stub page, with a stub login screen to land on. */
const renderAt = (route: string, isAuthenticated: boolean) =>
  render(
    <Routes>
      <Route element={<VerifyEmailRoute />}>
        <Route path="/verify-email" element={<div>verify page</div>} />
      </Route>
      <Route path="/login" element={<div>login page</div>} />
    </Routes>,
    {
      route,
      initialAuthState: { isAuthenticated, user: null, isLoading: false },
    }
  );

describe('VerifyEmailRoute', () => {
  it('lets a signed out visitor through when the URL carries a token', () => {
    renderAt('/verify-email?token=tok-1', false);
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('lets a signed in user through with a token too', () => {
    renderAt('/verify-email?token=tok-1', true);
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('still protects the bare request page from a signed out visitor', () => {
    renderAt('/verify-email', false);
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('shows the request page to a signed in user with no token', () => {
    renderAt('/verify-email', true);
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('treats an empty token as no token', () => {
    renderAt('/verify-email?token=', false);
    expect(screen.getByText('login page')).toBeInTheDocument();
  });
});
