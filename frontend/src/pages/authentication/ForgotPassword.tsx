import React, { useState } from 'react';
import AuthCard from '../../components/auth/AuthCard';
import AuthForm from '../../components/auth/AuthForm';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { Button } from '../../components/ui/button';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import { Input } from '../../components/ui/input';
import useApiRequest from '../../hooks/UseApiRequest';
import { requestPasswordReset } from '../../api/identityAuth';

function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [sentMessage, setSentMessage] = useState<string | null>(null);

  // Through `requestPasswordReset` rather than `authApi` directly, because the
  // service that mails the link is the only one that can confirm the token in
  // it. See that function's note: splitting the request and the confirm across
  // the two mechanisms produces a link that always fails.
  // Wrapped into the `{ data }` envelope `useApiRequest` unwraps, so the hook's
  // loading and error handling is reached unchanged. A refusal is thrown rather
  // than returned, because the hook renders a thrown message as the form error
  // and that is the same place a network failure would land.
  const forgotPasswordRequestFn = async (payload: { email: string }) => {
    const outcome = await requestPasswordReset(payload.email);
    if (!outcome.ok) throw new Error(outcome.message);
    return { data: outcome };
  };

  const {
    error: apiError,
    isLoading,
    executeRequest: sendPasswordResetLink,
    setError: setApiError,
  } = useApiRequest(forgotPasswordRequestFn);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null); // Clear previous errors

    if (!email.trim()) {
      setApiError('Email address cannot be empty.');
      return;
    }

    const result = await sendPasswordResetLink({ email: email });
    if (result) {
      // Successfully sent the link. The identity service fixes the wording it
      // returns in `detail`, so that sentence is rendered rather than a local
      // one when there is one.
      setSentMessage(result.message);
      setIsSubmitted(true);
    }
  };

  return (
    <AuthCard title="Forgot Password">
      {isSubmitted ? (
        <div>
          <ConfirmationAlert
            message={
              sentMessage ??
              'If an account with that email exists, a password reset link has been sent.'
            }
          />
          <AuthRedirectLink
            text="Remembered your password?"
            linkText="Sign In"
            to="/login"
          />
        </div>
      ) : (
        <>
          <AuthForm onSubmit={(e) => void handleSubmit(e)}>
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Email
              </label>
              <Input
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                type="email"
                name="email"
                disabled={isLoading}
              />
            </div>
            <ErrorAlert message={apiError} />
            <div>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Sending...' : 'Send Password Reset Link'}
              </Button>
            </div>
          </AuthForm>
          <AuthRedirectLink
            text="Remembered your password?"
            linkText="Sign In"
            to="/login"
          />
        </>
      )}
    </AuthCard>
  );
}
export default ForgotPassword;
