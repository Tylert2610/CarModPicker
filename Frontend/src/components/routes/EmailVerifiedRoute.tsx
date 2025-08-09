import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import LoadingSpinner from '../common/LoadingSpinner';

const EmailVerifiedRoute: React.FC = () => {
  const { isAuthenticated, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user?.email_verified) {
    return (
      <Navigate
        to="/verify-email"
        state={{
          from: location,
          message: 'Please verify your email to access this page.',
        }}
        replace
      />
    );
  }

  return <Outlet />;
};

export default EmailVerifiedRoute;
