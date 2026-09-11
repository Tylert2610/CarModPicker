/**
 * Landing page for a mailed password reset link in identity mode.
 *
 * Separate from `/forgot-password/confirm` because `RESET_PASSWORD_PATH` is
 * fixed by the identity service contract; both paths stay so links already in
 * a mailbox keep working. The token is read at render and spent on submit.
 */
import React, { useState } from 'react';
import { RESET_PASSWORD_PATH, readLinkToken } from '@webbpulse/auth';
import AuthCard from '../../components/auth/AuthCard';
import AuthForm from '../../components/auth/AuthForm';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { Button } from '../../components/ui/button';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import { Input } from '../../components/ui/input';
import { getIdentityClient } from '../../api/identityClient';

/**
 * The sentence shown for each refusal the package models. `password-rejected`
 * is separate from `invalid-link` because the two have different remedies.
 */
const REFUSAL_FALLBACKS: Record<string, string> = {
  'invalid-link':
    'This link is no longer valid. Reset links expire and can only be used once. Request a new one.',
  'password-rejected':
    'That password was rejected. Choose a longer or less common one, then request a new link.',
  'rate-limited':
    'Too many attempts. Wait a few minutes, then request a new reset link.',
  unavailable:
    'Email is not configured for this deployment, so reset links cannot be sent. Contact support.',
};

/**
 * Reads the token from the link, takes a new password, and spends the token
 * on submit.
 */
function ResetPassword() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const identity = getIdentityClient();
  const token = readLinkToken({ expectedPath: RESET_PASSWORD_PATH });

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (token === null) {
      setError('Missing reset token.');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError("Passwords don't match.");
      return;
    }
    if (!newPassword.trim()) {
      setError('Password cannot be empty.');
      return;
    }
    if (identity === null) {
      setError('Password reset is not available in this deployment.');
      return;
    }

    setIsSubmitting(true);
    try {
      const outcome = await identity.confirmPasswordReset({
        token,
        newPassword,
      });
      if (outcome.ok) {
        setIsDone(true);
        return;
      }
      setError(
        outcome.message ||
          REFUSAL_FALLBACKS[outcome.reason] ||
          'That reset link could not be used.'
      );
    } catch {
      setError(
        'Could not reach the server. Check your connection and try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (identity === null) {
    return (
      <AuthCard title="Set new password">
        <ErrorAlert message="Password reset is not available in this deployment." />
        <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
      </AuthCard>
    );
  }

  if (token === null) {
    return (
      <AuthCard title="Set new password">
        <ErrorAlert message="No reset token found. Please request a new link." />
        <AuthRedirectLink
          text="Request a"
          linkText="New Reset Link"
          to="/forgot-password"
        />
      </AuthCard>
    );
  }

  if (isDone) {
    return (
      <AuthCard title="Set new password">
        <ConfirmationAlert message="Your new password has been set, and every other session has been signed out. You can sign in now." />
        <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Set new password">
      <AuthForm onSubmit={(e) => void handleSubmit(e)}>
        <div>
          <label
            htmlFor="new-password"
            className="block text-sm font-medium text-foreground mb-2"
          >
            New Password
          </label>
          <Input
            id="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New Password"
            type="password"
            name="new-password"
            autoComplete="new-password"
            required
            disabled={isSubmitting}
          />
        </div>
        <div>
          <label
            htmlFor="confirm-new-password"
            className="block text-sm font-medium text-foreground mb-2"
          >
            Confirm New Password
          </label>
          <Input
            id="confirm-new-password"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
            placeholder="Confirm New Password"
            type="password"
            name="confirm-new-password"
            autoComplete="new-password"
            required
            disabled={isSubmitting}
          />
        </div>
        <ErrorAlert message={error} />
        <div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Setting Password...' : 'Set New Password'}
          </Button>
        </div>
      </AuthForm>
      <AuthRedirectLink
        text="Remembered your password?"
        linkText="Sign In"
        to="/login"
      />
    </AuthCard>
  );
}

export default ResetPassword;
