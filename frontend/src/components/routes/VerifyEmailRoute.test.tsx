// The gate that lets /verify-email serve two audiences.
//
// The regression this component exists to prevent: `ProtectedRoute` redirects a
// signed out visitor to /login carrying only the pathname, so a user who
// followed a mailed verification link would arrive with the token stripped and
// be told the link was invalid. The token is single use, so that is
// unrecoverable without asking for another email.
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
    // The whole point. A mailed link authenticates itself, and the person
    // clicking it is usually signed out and often on another device.
    renderAt('/verify-email?token=tok-1', false);
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('lets a signed in user through with a token too', () => {
    renderAt('/verify-email?token=tok-1', true);
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('still protects the bare request page from a signed out visitor', () => {
    // Unchanged behaviour: asking for a verification email needs a user,
    // because the address it sends to is that user's.
    renderAt('/verify-email', false);
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('shows the request page to a signed in user with no token', () => {
    renderAt('/verify-email', true);
    expect(screen.getByText('verify page')).toBeInTheDocument();
  });

  it('treats an empty token as no token', () => {
    // `?token=` with nothing after it cannot be confirmed, so it falls back to
    // the protected behaviour rather than rendering a page that will fail.
    renderAt('/verify-email?token=', false);
    expect(screen.getByText('login page')).toBeInTheDocument();
  });
});
