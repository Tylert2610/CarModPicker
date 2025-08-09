import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Input from '../../components/common/Input';
import ButtonStretch from '../../components/buttons/StretchButton';
import apiClient from '../../services/Api';
import AuthCard from '../../components/auth/AuthCard';
import { ErrorAlert, ConfirmationAlert } from '../../components/common/Alerts';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import useApiRequest from '../../hooks/UseApiRequest';
import AuthForm from '../../components/auth/AuthForm';
import type { NewPassword } from '../../types/Api';

function ForgotPasswordConfirm() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [searchParams] = useSearchParams();
  const [isSubmitted, setIsSubmitted] = useState(false);
  const token = searchParams.get('token');

  const forgotPasswordConfirmRequestFn = (payload: {
    token: string;
    newPasswordData: NewPassword;
  }) =>
    apiClient.post(
      `/auth/forgot-password/confirm?token=${payload.token}`,
      payload.newPasswordData
    );

  const {
    error: apiError,
    isLoading,
    executeRequest: confirmPasswordReset,
    setError: setApiError,
  } = useApiRequest<
    Record<string, never>,
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
      console.log('Password reset successful:', result);
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
          <AuthForm onSubmit={handleSubmit}>
            <Input
              label="New Password"
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
            <Input
              label="Confirm New Password"
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
            <ErrorAlert message={apiError} />
            <div>
              <ButtonStretch type="submit" disabled={isLoading}>
                {isLoading ? 'Setting Password...' : 'Set New Password'}
              </ButtonStretch>
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
