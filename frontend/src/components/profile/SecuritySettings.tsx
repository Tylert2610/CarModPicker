import { useState } from 'react';
import {
  FaChevronDown,
  FaChevronUp,
  FaLock,
  FaShieldAlt,
} from 'react-icons/fa';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { authApi } from '../../api/auth';
import { usersApi } from '../../api/users';
import type { TOTPSetupResponse } from '../../types/Api';
import SectionHeader from '../layout/SectionHeader';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { getApiErrorMessage } from '../../utils/apiError';

interface SecuritySettingsProps {
  onPasswordChanged: () => void;
  on2FAEnabled: () => void;
  on2FADisabled: () => void;
}

type TabType = 'password' | '2fa';

interface FieldProps {
  id: string;
  label: string;
  helperText?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

function Field({ id, label, helperText, icon, children }: FieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-foreground mb-2"
      >
        {label}
      </label>
      <div className="relative">
        {icon ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
          >
            {icon}
          </span>
        ) : null}
        {children}
      </div>
      {helperText ? (
        <div className="mt-2 text-sm text-muted-foreground">{helperText}</div>
      ) : null}
    </div>
  );
}

function SecuritySettings({
  onPasswordChanged,
  on2FAEnabled,
  on2FADisabled,
}: SecuritySettingsProps) {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('password');
  const [isExpanded, setIsExpanded] = useState(false);

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

  // 2FA state
  const [setupData, setSetupData] = useState<TOTPSetupResponse | null>(null);
  const [otp, setOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableOtp, setDisableOtp] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisabling, setIsDisabling] = useState(false);
  const [twoFAError, setTwoFAError] = useState<string | null>(null);
  const [twoFASuccess, setTwoFASuccess] = useState<string | null>(null);

  const setupRequestFn = () => authApi.setup2FA();
  const {
    error: setupError,
    isLoading: isSettingUp,
    executeRequest: performSetup,
  } = useApiRequest(setupRequestFn);

  const resetForms = () => {
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
          resetForms();
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

  // 2FA handlers
  const handleSetup = async () => {
    setTwoFAError(null);
    setTwoFASuccess(null);
    setOtp('');
    try {
      const result = await performSetup();
      if (result) {
        setSetupData(result);
      }
    } catch {
      // Error handled by useApiRequest
    }
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

    // Validation
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
        resetForms();
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

  return (
    <div className="space-y-4">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <SectionHeader title="Security Settings" />
        <button
          type="button"
          className="text-gray-400 hover:text-gray-300 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
        >
          {isExpanded ? <FaChevronUp /> : <FaChevronDown />}
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-6 animate-slideInUp">
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

              <Field
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
              </Field>

              <Field id="newPassword" label="New Password" icon={<FaLock />}>
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
              </Field>

              <Field
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
              </Field>

              {user?.totp_enabled && (
                <Field
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
                </Field>
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
                  onClick={resetForms}
                  disabled={isChangingPassword}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {/* 2FA Tab */}
          {activeTab === '2fa' && (
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

                  <Field
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
                  </Field>

                  <div className="flex space-x-2">
                    <Button
                      type="button"
                      onClick={() => void handleVerify()}
                      disabled={isVerifying || otp.length !== 6}
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
                    <Field
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
                    </Field>

                    <Field
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
                    </Field>
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
                    className="w-full"
                  >
                    {isDisabling ? 'Disabling...' : 'Disable 2FA'}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SecuritySettings;
