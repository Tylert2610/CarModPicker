import { useState } from 'react';
import AuthCard from '../../components/auth/AuthCard';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { Button } from '../../components/ui/button';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { apiClient } from '../../api/client';

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
      setIsSubmitted(true);
    }
  };

  if (authIsLoading) {
    return (
      <AuthCard title="Verify Your Email">
        <Spinner />
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
        <p className="mb-4 text-center text-muted-foreground">
          Click the button below to send a verification link to your email
          address: <strong>{user.email}</strong>.
        </p>
        {isSubmitted && !apiError && (
          <ConfirmationAlert message="Verification email sent! Please check your inbox." />
        )}
        <ErrorAlert message={apiError} />
        {!isSubmitted && (
          <Button
            type="button"
            className="w-full"
            onClick={() => void handleSubmit()}
            disabled={apiIsLoading}
          >
            {apiIsLoading ? 'Sending...' : 'Send Verification Email'}
          </Button>
        )}
        <AuthRedirectLink text="Back to" linkText="Home" to="/" />
      </div>
    </AuthCard>
  );
}
export default VerifyEmail;
