import { useEffect, useState } from 'react';
import { FaClock, FaKey, FaLink, FaLock, FaShieldAlt } from 'react-icons/fa';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { authApi } from '../../api/auth';
import { identityAvailability } from '../../api/authMode';
import { AUTH_MODE } from '../../api/authMode';
import IdentityTotpSettings from './IdentityTotpSettings';
import { usersApi } from '../../api/users';
import type { TOTPSetupResponse } from '../../types/Api';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import ConnectedAccountsSettings from './ConnectedAccountsSettings';
import IdentityConnectedAccounts from './IdentityConnectedAccounts';
import IdentityPasskeySettings from './IdentityPasskeySettings';
import PasskeySettings from './PasskeySettings';
import { getApiErrorMessage } from '../../utils/apiError';

const SESSION_EXPIRE_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: 'Use server default (60 min)' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
  { value: 240, label: '4 hours' },
  { value: 480, label: '8 hours' },
  { value: 1440, label: '24 hours' },
  { value: 10080, label: '7 days' },
];

interface SecuritySettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onPasswordChanged: () => void;
  on2FAEnabled: () => void;
  on2FADisabled: () => void;
  onSessionUpdated?: () => void;
}

type TabType = 'password' | '2fa' | 'passkeys' | 'connected' | 'session';

interface IconFieldProps {
  id: string;
  label: string;
  helperText?: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

/** A labelled form field with a leading icon and optional helper text. */
function IconField({ id, label, helperText, icon, children }: IconFieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-foreground mb-2"
      >
        {label}
      </label>
      <div className="relative">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
        >
          {icon}
        </span>
        {children}
      </div>
      {helperText ? (
        <div className="mt-2 text-sm text-muted-foreground">{helperText}</div>
      ) : null}
    </div>
  );
}

/**
 * The security dialog: password change, two-factor setup, and session controls.
 */
function SecuritySettingsDialog({
  isOpen,
  onClose,
  onPasswordChanged,
  on2FAEnabled,
  on2FADisabled,
  onSessionUpdated,
}: SecuritySettingsDialogProps) {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('password');
  const available = identityAvailability();

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: '',
    otp: '',
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  const [setupData, setSetupData] = useState<TOTPSetupResponse | null>(null);
  const [otp, setOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableOtp, setDisableOtp] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisabling, setIsDisabling] = useState(false);
  const [twoFAError, setTwoFAError] = useState<string | null>(null);
  const [twoFASuccess, setTwoFASuccess] = useState<string | null>(null);

  const [sessionExpireMinutes, setSessionExpireMinutes] = useState<
    number | null
  >(() => user?.session_expire_minutes ?? null);
  const [isSavingSession, setIsSavingSession] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionSuccess, setSessionSuccess] = useState<string | null>(null);

  const setupRequestFn = () => authApi.setup2FA();
  const {
    error: setupError,
    isLoading: isSettingUp,
    executeRequest: performSetup,
  } = useApiRequest(setupRequestFn);

  useEffect(() => {
    if (isOpen && user) {
      setSessionExpireMinutes(user.session_expire_minutes ?? null);
      setSessionError(null);
      setSessionSuccess(null);
    }
  }, [isOpen, user]);

  const handleClose = () => {
    setPasswordData({
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
      otp: '',
    });
    setPasswordError(null);
    setPasswordSuccess(null);

    setSetupData(null);
    setOtp('');
    setDisablePassword('');
    setDisableOtp('');
    setTwoFAError(null);
    setTwoFASuccess(null);

    setSessionError(null);
    setSessionSuccess(null);

    onClose();
  };

  const handleSaveSession = async () => {
    if (!user) return;
    setSessionError(null);
    setSessionSuccess(null);
    setIsSavingSession(true);
    try {
      await usersApi.updateUser(user.id, {
        session_expire_minutes: sessionExpireMinutes,
      });
      setSessionSuccess(
        'Session length updated. Your current session has been extended with the new expiry.'
      );
      onSessionUpdated?.();
    } catch (err: unknown) {
      setSessionError(
        getApiErrorMessage(err, 'Failed to update session length.')
      );
    } finally {
      setIsSavingSession(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!passwordData.currentPassword.trim()) {
      setPasswordError('Current password is required.');
      return;
    }

    if (!passwordData.newPassword.trim()) {
      setPasswordError('New password is required.');
      return;
    }

    if (passwordData.newPassword !== passwordData.confirmNewPassword) {
      setPasswordError("New passwords don't match.");
      return;
    }

    if (passwordData.newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }

    if (user?.totp_enabled) {
      if (!passwordData.otp.trim() || passwordData.otp.length !== 6) {
        setPasswordError(
          '2FA is enabled. Please enter a valid 6-digit OTP code.'
        );
        return;
      }
    }

    setIsChangingPassword(true);

    try {
      const updateData: {
        current_password: string;
        password: string;
        otp?: string;
      } = {
        current_password: passwordData.currentPassword,
        password: passwordData.newPassword,
      };

      if (user?.totp_enabled) {
        updateData.otp = passwordData.otp;
      }

      const response = await usersApi.updateUser(user!.id, updateData);

      if (response.data) {
        setPasswordSuccess('Password changed successfully!');
        setTimeout(() => {
          setPasswordData({
            currentPassword: '',
            newPassword: '',
            confirmNewPassword: '',
            otp: '',
          });
          onPasswordChanged();
        }, 1500);
      }
    } catch (err: unknown) {
      let errorMessage = 'Failed to change password';
      if (err instanceof Error) {
        errorMessage = err.message;
      } else if (typeof err === 'object' && err !== null && 'response' in err) {
        errorMessage = getApiErrorMessage(err, errorMessage);
      }
      setPasswordError(errorMessage);
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleSetup = async () => {
    setTwoFAError(null);
    setTwoFASuccess(null);
    setOtp('');
    try {
      const result = await performSetup();
      if (result) {
        setSetupData(result);
      }
      // eslint-disable-next-line no-empty
    } catch {}
  };

  const handleVerify = async () => {
    if (!otp.trim() || otp.length !== 6) {
      setTwoFAError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setTwoFAError(null);
    setIsVerifying(true);

    try {
      await authApi.verify2FA({ otp });
      setTwoFASuccess('2FA has been enabled successfully!');
      setSetupData(null);
      setOtp('');
      setTimeout(() => {
        on2FAEnabled();
      }, 1500);
    } catch (err: unknown) {
      setTwoFAError(
        getApiErrorMessage(err, 'Invalid OTP code. Please try again.')
      );
    } finally {
      setIsVerifying(false);
    }
  };

  const handleDisable = async () => {
    setTwoFAError(null);
    setTwoFASuccess(null);

    if (!disablePassword.trim()) {
      setTwoFAError('Password is required to disable 2FA.');
      return;
    }

    if (!disableOtp.trim() || disableOtp.length !== 6) {
      setTwoFAError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setIsDisabling(true);

    try {
      await authApi.disable2FA({
        password: disablePassword,
        otp: disableOtp,
      });
      setTwoFASuccess('2FA has been disabled successfully!');
      setTimeout(() => {
        setDisablePassword('');
        setDisableOtp('');
        on2FADisabled();
      }, 1500);
    } catch (err: unknown) {
      setTwoFAError(
        getApiErrorMessage(err, 'Failed to disable 2FA. Please try again.')
      );
    } finally {
      setIsDisabling(false);
    }
  };

  if (!isOpen) return null;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Security Settings</DialogTitle>
        </DialogHeader>
        <div className="space-y-6">
          <div className="flex border-b border-gray-700">
            <button
              type="button"
              onClick={() => setActiveTab('password')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'password'
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              <div className="flex items-center justify-center space-x-2">
                <FaLock />
                <span>Change Password</span>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('2fa')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === '2fa'
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              <div className="flex items-center justify-center space-x-2">
                <FaShieldAlt />
                <span>Two-Factor Authentication</span>
              </div>
            </button>
            {available.passkeys && (
              <button
                type="button"
                onClick={() => setActiveTab('passkeys')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'passkeys'
                    ? 'text-primary border-b-2 border-primary'
                    : 'text-gray-400 hover:text-gray-300'
                }`}
              >
                <div className="flex items-center justify-center space-x-2">
                  <FaKey />
                  <span>Passkeys</span>
                </div>
              </button>
            )}
            {available.googleOauth && (
              <button
                type="button"
                onClick={() => setActiveTab('connected')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'connected'
                    ? 'text-primary border-b-2 border-primary'
                    : 'text-gray-400 hover:text-gray-300'
                }`}
              >
                <div className="flex items-center justify-center space-x-2">
                  <FaLink />
                  <span>Connected</span>
                </div>
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveTab('session')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'session'
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              <div className="flex items-center justify-center space-x-2">
                <FaClock />
                <span>Session</span>
              </div>
            </button>
          </div>

          {activeTab === 'password' && (
            <form
              onSubmit={(e) => void handlePasswordChange(e)}
              className="space-y-6"
            >
              {passwordSuccess && (
                <ConfirmationAlert message={passwordSuccess} />
              )}
              {passwordError && <ErrorAlert message={passwordError} />}

              <IconField
                id="currentPassword"
                label="Current Password"
                icon={<FaLock />}
              >
                <Input
                  id="currentPassword"
                  name="currentPassword"
                  type="password"
                  value={passwordData.currentPassword}
                  onChange={(e) => {
                    setPasswordData((prev) => ({
                      ...prev,
                      currentPassword: e.target.value,
                    }));
                    setPasswordError(null);
                  }}
                  disabled={isChangingPassword}
                  required
                  autoComplete="current-password"
                  className="pl-10"
                />
              </IconField>

              <IconField
                id="newPassword"
                label="New Password"
                icon={<FaLock />}
              >
                <Input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  value={passwordData.newPassword}
                  onChange={(e) => {
                    setPasswordData((prev) => ({
                      ...prev,
                      newPassword: e.target.value,
                    }));
                    setPasswordError(null);
                  }}
                  disabled={isChangingPassword}
                  required
                  autoComplete="new-password"
                  minLength={8}
                  className="pl-10"
                />
              </IconField>

              <IconField
                id="confirmNewPassword"
                label="Confirm New Password"
                icon={<FaLock />}
              >
                <Input
                  id="confirmNewPassword"
                  name="confirmNewPassword"
                  type="password"
                  value={passwordData.confirmNewPassword}
                  onChange={(e) => {
                    setPasswordData((prev) => ({
                      ...prev,
                      confirmNewPassword: e.target.value,
                    }));
                    setPasswordError(null);
                  }}
                  disabled={isChangingPassword}
                  required
                  autoComplete="new-password"
                  className="pl-10"
                />
              </IconField>

              {user?.totp_enabled && (
                <IconField
                  id="otp"
                  label="2FA Code"
                  icon={<FaShieldAlt />}
                  helperText="Enter the 6-digit code from your authenticator app"
                >
                  <Input
                    id="otp"
                    name="otp"
                    type="text"
                    value={passwordData.otp}
                    onChange={(e) => {
                      const value = e.target.value
                        .replace(/\D/g, '')
                        .slice(0, 6);
                      setPasswordData((prev) => ({ ...prev, otp: value }));
                      setPasswordError(null);
                    }}
                    placeholder="000000"
                    disabled={isChangingPassword}
                    required
                    maxLength={6}
                    className="pl-10"
                  />
                </IconField>
              )}

              <div className="flex space-x-3 pt-4">
                <Button
                  type="submit"
                  disabled={isChangingPassword}
                  loading={isChangingPassword}
                  className="flex-1"
                >
                  {isChangingPassword
                    ? 'Changing Password...'
                    : 'Change Password'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleClose}
                  disabled={isChangingPassword}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {activeTab === '2fa' && AUTH_MODE === 'identity' && (
            <IdentityTotpSettings
              enabled={user?.totp_enabled === true}
              onChanged={() => {
                if (user?.totp_enabled === true) {
                  on2FADisabled();
                } else {
                  on2FAEnabled();
                }
              }}
            />
          )}
          {activeTab === '2fa' && AUTH_MODE !== 'identity' && (
            <div className="space-y-6">
              {twoFASuccess && <ConfirmationAlert message={twoFASuccess} />}
              {(twoFAError || setupError) && (
                <ErrorAlert
                  message={twoFAError || setupError || 'An error occurred'}
                />
              )}

              {!user?.totp_enabled && !setupData && (
                <div className="space-y-4">
                  <div className="flex items-center space-x-3 text-gray-300">
                    <FaShieldAlt className="text-primary text-2xl" />
                    <div>
                      <h3 className="text-lg font-semibold">
                        Enable Two-Factor Authentication
                      </h3>
                      <p className="text-sm text-gray-400">
                        Add an extra layer of security to your account by
                        requiring a code from your authenticator app when you
                        log in.
                      </p>
                    </div>
                  </div>

                  <div className="bg-gray-800/50 rounded-lg p-4 space-y-2 text-sm text-gray-300">
                    <p className="font-semibold">How it works:</p>
                    <ol className="list-decimal list-inside space-y-1 ml-2">
                      <li>
                        Scan the QR code with an authenticator app (Google
                        Authenticator, Authy, etc.)
                      </li>
                      <li>
                        Enter the 6-digit code from your app to verify and
                        enable 2FA
                      </li>
                      <li>You'll need this code every time you log in</li>
                    </ol>
                  </div>

                  <Button
                    type="button"
                    onClick={() => void handleSetup()}
                    disabled={isSettingUp}
                    loading={isSettingUp}
                    className="w-full"
                  >
                    {isSettingUp ? 'Setting up...' : 'Set Up 2FA'}
                  </Button>
                </div>
              )}

              {!user?.totp_enabled && setupData && (
                <div className="space-y-4">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-gray-300 mb-2">
                      Scan this QR code
                    </h3>
                    <div className="flex justify-center mb-4">
                      <img
                        src={setupData.qr_code_data}
                        alt="2FA QR Code"
                        className="border-2 border-gray-700 rounded-lg p-2 bg-white"
                      />
                    </div>
                    <p className="text-sm text-gray-400 mb-2">
                      Or enter this code manually:
                    </p>
                    <p className="text-sm font-mono text-primary bg-gray-800/50 p-2 rounded">
                      {setupData.manual_entry_key}
                    </p>
                  </div>

                  <IconField
                    id="setup-otp"
                    label="Enter 6-digit code from your app"
                    icon={<FaShieldAlt />}
                  >
                    <Input
                      id="setup-otp"
                      name="otp"
                      type="text"
                      value={otp}
                      onChange={(e) => {
                        const value = e.target.value
                          .replace(/\D/g, '')
                          .slice(0, 6);
                        setOtp(value);
                      }}
                      placeholder="000000"
                      maxLength={6}
                      className="pl-10"
                    />
                  </IconField>

                  <div className="flex space-x-2">
                    <Button
                      type="button"
                      onClick={() => void handleVerify()}
                      disabled={isVerifying || otp.length !== 6}
                      loading={isVerifying}
                      className="flex-1"
                    >
                      {isVerifying ? 'Verifying...' : 'Verify & Enable'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setSetupData(null);
                        setOtp('');
                        setTwoFAError(null);
                      }}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {user?.totp_enabled && (
                <div className="space-y-4">
                  <div className="flex items-center space-x-3 text-gray-300">
                    <FaShieldAlt className="text-green-400 text-2xl" />
                    <div>
                      <h3 className="text-lg font-semibold">2FA is Enabled</h3>
                      <p className="text-sm text-gray-400">
                        Your account is protected with two-factor
                        authentication.
                      </p>
                    </div>
                  </div>

                  <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4">
                    <p className="text-sm text-yellow-300">
                      <strong>Warning:</strong> Disabling 2FA will remove this
                      security feature from your account. Make sure you have
                      backup codes or another way to secure your account.
                    </p>
                  </div>

                  <div className="space-y-4">
                    <IconField
                      id="disablePassword"
                      label="Password"
                      icon={<FaLock />}
                    >
                      <Input
                        id="disablePassword"
                        name="disablePassword"
                        type="password"
                        value={disablePassword}
                        onChange={(e) => {
                          setDisablePassword(e.target.value);
                          setTwoFAError(null);
                        }}
                        placeholder="Enter your password"
                        disabled={isDisabling}
                        required
                        autoComplete="current-password"
                        className="pl-10"
                      />
                    </IconField>

                    <IconField
                      id="disableOtp"
                      label="2FA Code"
                      icon={<FaShieldAlt />}
                      helperText="Enter the 6-digit code from your authenticator app"
                    >
                      <Input
                        id="disableOtp"
                        name="disableOtp"
                        type="text"
                        value={disableOtp}
                        onChange={(e) => {
                          const value = e.target.value
                            .replace(/\D/g, '')
                            .slice(0, 6);
                          setDisableOtp(value);
                          setTwoFAError(null);
                        }}
                        placeholder="000000"
                        disabled={isDisabling}
                        required
                        maxLength={6}
                        className="pl-10"
                      />
                    </IconField>
                  </div>

                  <Button
                    type="button"
                    variant="destructive"
                    onClick={() => void handleDisable()}
                    disabled={
                      isDisabling ||
                      !disablePassword.trim() ||
                      disableOtp.length !== 6
                    }
                    loading={isDisabling}
                    className="w-full"
                  >
                    {isDisabling ? 'Disabling...' : 'Disable 2FA'}
                  </Button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'session' && (
            <div className="space-y-6">
              {sessionSuccess && <ConfirmationAlert message={sessionSuccess} />}
              {sessionError && <ErrorAlert message={sessionError} />}

              <div className="flex items-center space-x-3 text-gray-300">
                <FaClock className="text-primary text-2xl" />
                <div>
                  <h3 className="text-lg font-semibold">Session length</h3>
                  <p className="text-sm text-gray-400">
                    Choose how long you stay signed in. Shorter sessions are
                    more secure. A new token with the selected expiry is issued
                    when you save.
                  </p>
                </div>
              </div>

              <div>
                <label
                  htmlFor="session-expire"
                  className="block text-sm font-medium text-gray-300 mb-2"
                >
                  Stay signed in for
                </label>
                <select
                  id="session-expire"
                  value={sessionExpireMinutes ?? ''}
                  onChange={(e) => {
                    const v = e.target.value;
                    setSessionExpireMinutes(v === '' ? null : Number(v));
                    setSessionError(null);
                  }}
                  disabled={isSavingSession}
                  className="block w-full rounded-lg border border-gray-600 bg-gray-800 px-4 py-2 text-gray-300 focus:border-primary focus:ring-1 focus:ring-primary"
                >
                  {SESSION_EXPIRE_OPTIONS.map((opt) => (
                    <option
                      key={opt.value ?? 'default'}
                      value={opt.value ?? ''}
                    >
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <Button
                type="button"
                onClick={() => void handleSaveSession()}
                disabled={isSavingSession}
                loading={isSavingSession}
                className="w-full"
              >
                {isSavingSession ? 'Saving...' : 'Save session length'}
              </Button>
            </div>
          )}
          {available.passkeys &&
            activeTab === 'passkeys' &&
            (AUTH_MODE === 'identity' ? (
              <IdentityPasskeySettings />
            ) : (
              <PasskeySettings />
            ))}
          {available.googleOauth &&
            activeTab === 'connected' &&
            (AUTH_MODE === 'identity' ? (
              <IdentityConnectedAccounts />
            ) : (
              <ConnectedAccountsSettings />
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default SecuritySettingsDialog;
