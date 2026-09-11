import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import AuthForm from '../../components/auth/AuthForm';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { Button } from '../../components/ui/button';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import { Input } from '../../components/ui/input';
import useApiRequest from '../../hooks/UseApiRequest';
import { authApi } from '../../api/auth';
import type { NewPassword } from '../../types/Api';

/** Landing page for CarModPicker's own reset link, where a new password is set. */
function ForgotPasswordConfirm() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [searchParams] = useSearchParams();
  const [isSubmitted, setIsSubmitted] = useState(false);
  const token = searchParams.get('token');

  const forgotPasswordConfirmRequestFn = (payload: {
    token: string;
    newPasswordData: NewPassword;
  }) => authApi.resetPasswordConfirm(payload.token, payload.newPasswordData);

  const {
    error: apiError,
    isLoading,
    executeRequest: confirmPasswordReset,
    setError: setApiError,
  } = useApiRequest<
    Record<string, string>,
    { token: string; newPasswordData: NewPassword }
  >(forgotPasswordConfirmRequestFn);

  useEffect(() => {
    if (!token) {
      setApiError('No reset token found. Please request a new link.');
    }
  }, [token, setApiError]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (!token) {
      setApiError('Missing reset token.');
      return;
    }

    if (newPassword !== confirmNewPassword) {
      setApiError("Passwords don't match.");
      return;
    }
    if (!newPassword.trim()) {
      setApiError('Password cannot be empty.');
      return;
    }

    const payload: NewPassword = { password: newPassword };
    const result = await confirmPasswordReset({
      token: token,
      newPasswordData: payload,
    });

    if (result) {
      setIsSubmitted(true);
    }
  };

  return (
    <AuthCard title="Set new password">
      {!token ? (
        <>
          <ErrorAlert
            message={
              apiError || 'No reset token found. Please request a new link.'
            }
          />
          <AuthRedirectLink
            text="Request a"
            linkText="New Reset Link"
            to="/forgot-password"
          />
        </>
      ) : isSubmitted ? (
        <div>
          <ConfirmationAlert message="Your new password has been set. You can now sign in." />
          <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
        </div>
      ) : (
        <>
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
                disabled={isLoading}
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
                disabled={isLoading}
              />
            </div>
            <ErrorAlert message={apiError} />
            <div>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Setting Password...' : 'Set New Password'}
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
export default ForgotPasswordConfirm;
