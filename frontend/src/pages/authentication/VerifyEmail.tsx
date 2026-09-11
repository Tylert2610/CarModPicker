/**
 * The `/verify-email` page, which serves two behaviours on one path.
 *
 * A `?token=` query means a mailed link landed here and `VerifyEmailToken`
 * handles it; anything else is a signed in user requesting a fresh email.
 * The path is fixed by `VERIFY_EMAIL_PATH` in the identity contract.
 */
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { LINK_TOKEN_PARAM } from '@webbpulse/auth';
import AuthCard from '../../components/auth/AuthCard';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { Button } from '../../components/ui/button';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { requestVerificationEmail } from '../../api/identityAuth';
import VerifyEmailToken from './VerifyEmailToken';

/** Routes `/verify-email` to the token confirmation or the request form. */
function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { user, isLoading: authIsLoading } = useAuth();
  const linkToken = searchParams.get(LINK_TOKEN_PARAM);

  const verifyEmailRequestFn = async (payload: { email: string }) => {
    const outcome = await requestVerificationEmail(payload.email);
    if (!outcome.ok) throw new Error(outcome.message);
    return { data: outcome };
  };

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
    setApiError(null);
    setIsSubmitted(false);

    const result = await sendEmailVerificationLink({ email: user.email });
    if (result) {
      setIsSubmitted(true);
    }
  };

  if (linkToken !== null && linkToken !== '') {
    return <VerifyEmailToken />;
  }

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
