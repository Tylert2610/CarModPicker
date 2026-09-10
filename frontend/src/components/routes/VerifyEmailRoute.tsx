/**
 * The auth gate for `/verify-email`, which needs two different gates.
 *
 * That one path serves two things (see `pages/authentication/VerifyEmail`).
 * Asking for a verification email requires a signed in user, because the
 * address it sends to is that user's. Confirming a mailed link requires the
 * opposite: the person clicking it is usually not signed in, often on a
 * different device from the one they registered on, and the link itself is the
 * only credential the flow has or needs.
 *
 * So `ProtectedRoute` is right for one and wrong for the other, and this
 * component picks between them on the same signal the page does: a `?token=`
 * in the query string. Without one it delegates to `ProtectedRoute` unchanged,
 * which keeps the existing behaviour exactly as it was. With one it renders the
 * page directly, so a mailed link is never bounced to the login screen and back
 * with its single use token stripped by the redirect.
 *
 * That last part is the bug this component exists to prevent: `ProtectedRoute`
 * redirects to `/login` carrying only the pathname in `state.from`, so a user
 * who followed a verification link while signed out would lose the token and be
 * told the link was invalid.
 */
import React from 'react';
import { Outlet, useSearchParams } from 'react-router-dom';
import { LINK_TOKEN_PARAM } from '@webbpulse/auth';
import ProtectedRoute from './ProtectedRoute';

const VerifyEmailRoute: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get(LINK_TOKEN_PARAM);
  // A mailed link authenticates itself. Anything else is a signed in user
  // asking for one, which is what `ProtectedRoute` already gates correctly.
  if (token !== null && token !== '') {
    return <Outlet />;
  }
  return <ProtectedRoute />;
};

export default VerifyEmailRoute;
