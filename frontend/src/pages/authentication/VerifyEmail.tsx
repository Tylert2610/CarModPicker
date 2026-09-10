/**
 * The `/verify-email` page, which is two pages sharing one path.
 *
 * CarModPicker has always used this path for "send me a verification email",
 * reached by a signed in user whose address is not yet verified. In identity
 * mode the same path is also where a mailed verification link lands, because
 * `VERIFY_EMAIL_PATH` in `@webbpulse/auth` is `/verify-email` and the backend
 * concatenates it onto the frontend base when it builds the URL it sends. That
 * constant is a contract across two repositories and this application does not
 * get to pick a different path for it.
 *
 * So the query string decides. A `?token=` came from an email and is a
 * confirmation, handled by `VerifyEmailToken`. Anything else is the request
 * form below, unchanged from what it has always been.
 *
 * The dispatch is deliberately not gated on the mode. In bearer mode no link
 * ever arrives carrying a token, so the branch is unreachable rather than
 * wrong, and a mode check here would be a second place to update at cutover.
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
import { apiClient } from '../../api/client';
import VerifyEmailToken from './VerifyEmailToken';

function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { user, isLoading: authIsLoading } = useAuth(); // Get user from auth context
  const linkToken = searchParams.get(LINK_TOKEN_PARAM);

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

  // A token in the query string means this is a mailed link rather than a
  // person asking for one. Checked before the loading and signed in guards
  // below, because confirming a link needs neither: the link is the proof.
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
