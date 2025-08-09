import { useState } from 'react';
import AuthCard from '../../components/auth/AuthCard';
import { ErrorAlert, ConfirmationAlert } from '../../components/common/Alerts';
import ButtonStretch from '../../components/buttons/StretchButton';
import apiClient from '../../services/Api';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../contexts/AuthContext'; 
import LoadingSpinner from '../../components/common/LoadingSpinner'; 

function VerifyEmail() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { user, isLoading: authIsLoading } = useAuth(); // Get user from auth context

  const verifyEmailRequestFn = (payload: { email: string }) =>
    apiClient.post<Record<string, never>>('/auth/verify-email', payload);

  const {
    error: apiError,
    isLoading: apiIsLoading,
    executeRequest: sendEmailVerificationLink,
    setError: setApiError,
  } = useApiRequest(verifyEmailRequestFn);

  const handleSubmit = async () => {
    if (!user || !user.email) {
      setApiError('User email not found. Please log in again.');
      return;
    }
    setApiError(null); // Clear previous errors
    setIsSubmitted(false);

    const result = await sendEmailVerificationLink({ email: user.email });
    if (result) {
      // Successfully sent the link
      console.log('Email verification link sent:', result);
      setIsSubmitted(true);
    }
  };

  if (authIsLoading) {
    return (
      <AuthCard title="Verify Your Email">
        <LoadingSpinner />
      </AuthCard>
    );
  }

  if (!user) {
    return (
      <AuthCard title="Verify Your Email">
        <ErrorAlert message="User not found. Please log in." />
        <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
      </AuthCard>
    );
  }

  if (user.email_verified && !isSubmitted) {
    return (
      <AuthCard title="Email Already Verified">
        <ConfirmationAlert message="Your email address has already been verified." />
        <AuthRedirectLink text="Go to" linkText="Profile" to="/profile" />
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Verify Your Email">
      <div>
        <p className="mb-4 text-center text-gray-300">
          Click the button below to send a verification link to your email
          address: <strong>{user.email}</strong>.
        </p>
        {isSubmitted && !apiError && (
          <ConfirmationAlert message="Verification email sent! Please check your inbox." />
        )}
        <ErrorAlert message={apiError} />
        {!isSubmitted && (
          <ButtonStretch onClick={handleSubmit} disabled={apiIsLoading}>
            {apiIsLoading ? 'Sending...' : 'Send Verification Email'}
          </ButtonStretch>
        )}
        <AuthRedirectLink text="Back to" linkText="Home" to="/" />
      </div>
    </AuthCard>
  );
}
export default VerifyEmail;
