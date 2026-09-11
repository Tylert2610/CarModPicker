import { useEffect, useState } from 'react';
import { FaClock, FaKey, FaLink, FaLock, FaShieldAlt } from 'react-icons/fa';
import { useAuth } from '../../hooks/useAuth';
import { identityAvailability } from '../../api/authMode';
import IdentityTotpSettings from './IdentityTotpSettings';
import { usersApi } from '../../api/users';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import IdentityConnectedAccounts from './IdentityConnectedAccounts';
import IdentityPasskeySettings from './IdentityPasskeySettings';
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
  // Both mechanisms carry passkeys and connected accounts, and the panels for
  // each speak entirely different routes, so the tab picks a component rather
  // than branching inside one. See `./IdentityPasskeySettings` and
  // `./IdentityConnectedAccounts` for why they are separate files.
  const available = identityAvailability();

  // Password change state
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: '',
    otp: '',
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  // Session expiry state
  const [sessionExpireMinutes, setSessionExpireMinutes] = useState<
    number | null
  >(() => user?.session_expire_minutes ?? null);
  const [isSavingSession, setIsSavingSession] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionSuccess, setSessionSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && user) {
      setSessionExpireMinutes(user.session_expire_minutes ?? null);
      setSessionError(null);
      setSessionSuccess(null);
    }
  }, [isOpen, user]);

  const handleClose = () => {
    // Reset password form
    setPasswordData({
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
      otp: '',
    });
    setPasswordError(null);
    setPasswordSuccess(null);

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

  // Password change handlers
  const handlePasswordChange = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    // Validation
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

    // If 2FA is enabled, require OTP
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

      // Include OTP if 2FA is enabled
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
          {/* Tabs */}
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

          {/* Password Change Tab */}
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

          {/* 2FA Tab. The identity service takes only a code to disable a
              factor, hands back a provisioning URI for the client to draw, and
              issues recovery codes. Row 13 of `docs/identity-adoption.md`
              deleted the legacy flow that used to render here instead. See
              IdentityTotpSettings. */}
          {activeTab === '2fa' && (
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

          {/* Session Tab */}
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
          {available.passkeys && activeTab === 'passkeys' && (
            <IdentityPasskeySettings />
          )}
          {available.googleOauth && activeTab === 'connected' && (
            <IdentityConnectedAccounts />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default SecuritySettingsDialog;
