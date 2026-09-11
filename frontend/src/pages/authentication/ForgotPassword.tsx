import React, { useState } from 'react';
import AuthCard from '../../components/auth/AuthCard';
import AuthForm from '../../components/auth/AuthForm';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { Button } from '../../components/ui/button';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import { Input } from '../../components/ui/input';
import useApiRequest from '../../hooks/UseApiRequest';
import { requestPasswordReset } from '../../api/identityAuth';

/** Form that requests a password reset link for an email address. */
function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [sentMessage, setSentMessage] = useState<string | null>(null);

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
    setApiError(null);

    if (!email.trim()) {
      setApiError('Email address cannot be empty.');
      return;
    }

    const result = await sendPasswordResetLink({ email: email });
    if (result) {
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
