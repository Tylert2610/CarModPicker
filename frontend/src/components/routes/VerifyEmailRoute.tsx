/**
 * The auth gate for `/verify-email`, which serves two flows. With a `?token=`
 * it renders the page directly, so a mailed link is never bounced through login
 * and stripped of its single use token; without one it delegates to ProtectedRoute.
 */
import React from 'react';
import { Outlet, useSearchParams } from 'react-router-dom';
import { LINK_TOKEN_PARAM } from '@webbpulse/auth';
import ProtectedRoute from './ProtectedRoute';

/** Picks the gate for /verify-email on the presence of a `?token=`. */
const VerifyEmailRoute: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get(LINK_TOKEN_PARAM);
  if (token !== null && token !== '') {
    return <Outlet />;
  }
  return <ProtectedRoute />;
};

export default VerifyEmailRoute;
