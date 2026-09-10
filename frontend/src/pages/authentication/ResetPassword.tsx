/**
 * The page a mailed password reset link lands on in identity mode.
 *
 * ## Why this is a second page rather than a change to ForgotPasswordConfirm
 *
 * `RESET_PASSWORD_PATH` in `@webbpulse/auth` is `/reset-password`, and the
 * backend concatenates it onto the frontend base when it builds the mailed URL,
 * so that path is fixed by a contract this application does not own.
 * CarModPicker's own reset link lands on `/forgot-password/confirm` and calls
 * `/auth/reset-password/confirm`, a route the identity service does not serve.
 *
 * Both stay. `/forgot-password/confirm` keeps working for every link already
 * sitting in a mailbox, which matters because a reset link outlives the deploy
 * that sent it, and this page serves the links the identity service sends.
 * Folding them into one page would mean one component holding two token
 * formats and two endpoints, and the older of the two goes away entirely at the
 * end of the migration rather than being maintained.
 *
 * ## Why the token is read at first render but spent only on submit
 *
 * Unlike verification, a reset needs a new password, so there is a form and the
 * token is spent when it is submitted. Reading it early is what lets the page
 * say "this link is missing its token" before the user types a password it is
 * going to throw away.
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
 * The sentence for each refusal the package models.
 *
 * `password-rejected` is deliberately separate from `invalid-link` even though
 * both mean the link is now spent, because the remedies differ: one is "ask for
 * another link", the other is "ask for another link and pick a better
 * password", and only the second is the user's own doing.
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

function ResetPassword() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const identity = getIdentityClient();
  // `expectedPath` keeps a verification token from being read off this page and
  // presented to the reset endpoint, which the server refuses as a
  // wrong-purpose token.
  const token = readLinkToken({ expectedPath: RESET_PASSWORD_PATH });

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (token === null) {
      setError('Missing reset token.');
      return;
    }
    // Checked here rather than by the server, because sending a password the
    // user has already contradicted would spend the single use token on an
    // attempt that cannot succeed.
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
