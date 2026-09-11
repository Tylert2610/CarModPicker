import { useState } from 'react';
import { FaLock, FaShieldAlt } from 'react-icons/fa';
import useApiRequest from '../../hooks/UseApiRequest';
import { authApi } from '../../api/auth';
import type { TOTPSetupResponse } from '../../types/Api';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { getApiErrorMessage } from '../../utils/apiError';

interface TwoFactorAuthDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onEnabled: () => void;
  onDisabled: () => void;
  isEnabled: boolean;
}

/**
 * The legacy two-factor dialog, which takes the account password alongside the code.
 */
function TwoFactorAuthDialog({
  isOpen,
  onClose,
  onEnabled,
  onDisabled,
  isEnabled,
}: TwoFactorAuthDialogProps) {
  const [setupData, setSetupData] = useState<TOTPSetupResponse | null>(null);
  const [otp, setOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableOtp, setDisableOtp] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisabling, setIsDisabling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const setupRequestFn = () => authApi.setup2FA();
  const {
    error: setupError,
    isLoading: isSettingUp,
    executeRequest: performSetup,
  } = useApiRequest(setupRequestFn);

  const handleSetup = async () => {
    setError(null);
    setSuccess(null);
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
      setError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setError(null);
    setIsVerifying(true);

    try {
      await authApi.verify2FA({ otp });
      setSuccess('2FA has been enabled successfully!');
      setSetupData(null);
      setOtp('');
      setTimeout(() => {
        onEnabled();
        onClose();
      }, 1500);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Invalid OTP code. Please try again.'));
    } finally {
      setIsVerifying(false);
    }
  };

  const handleDisable = async () => {
    setError(null);
    setSuccess(null);

    if (!disablePassword.trim()) {
      setError('Password is required to disable 2FA.');
      return;
    }

    if (!disableOtp.trim() || disableOtp.length !== 6) {
      setError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setIsDisabling(true);

    try {
      await authApi.disable2FA({
        password: disablePassword,
        otp: disableOtp,
      });
      setSuccess('2FA has been disabled successfully!');
      setTimeout(() => {
        setDisablePassword('');
        setDisableOtp('');
        onDisabled();
        onClose();
      }, 1500);
    } catch (err: unknown) {
      setError(
        getApiErrorMessage(err, 'Failed to disable 2FA. Please try again.')
      );
    } finally {
      setIsDisabling(false);
    }
  };

  const handleClose = () => {
    setSetupData(null);
    setOtp('');
    setDisablePassword('');
    setDisableOtp('');
    setError(null);
    setSuccess(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Two-Factor Authentication</DialogTitle>
        </DialogHeader>
        <div className="space-y-6">
          {success && <ConfirmationAlert message={success} />}
          {(error || setupError) && (
            <ErrorAlert message={error || setupError || 'An error occurred'} />
          )}

          {!isEnabled && !setupData && (
            <div className="space-y-4">
              <div className="flex items-center space-x-3 text-gray-300">
                <FaShieldAlt className="text-primary text-2xl" />
                <div>
                  <h3 className="text-lg font-semibold">
                    Enable Two-Factor Authentication
                  </h3>
                  <p className="text-sm text-gray-400">
                    Add an extra layer of security to your account by requiring
                    a code from your authenticator app when you log in.
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
                    Enter the 6-digit code from your app to verify and enable
                    2FA
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

          {!isEnabled && setupData && (
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

              <div>
                <label
                  htmlFor="2fa-setup-otp"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Enter 6-digit code from your app
                </label>
                <div className="relative">
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
                  >
                    <FaShieldAlt />
                  </span>
                  <Input
                    id="2fa-setup-otp"
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
                </div>
              </div>

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
                    setError(null);
                  }}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {isEnabled && (
            <div className="space-y-4">
              <div className="flex items-center space-x-3 text-gray-300">
                <FaShieldAlt className="text-green-400 text-2xl" />
                <div>
                  <h3 className="text-lg font-semibold">2FA is Enabled</h3>
                  <p className="text-sm text-gray-400">
                    Your account is protected with two-factor authentication.
                  </p>
                </div>
              </div>

              <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4">
                <p className="text-sm text-yellow-300">
                  <strong>Warning:</strong> Disabling 2FA will remove this
                  security feature from your account. Make sure you have backup
                  codes or another way to secure your account.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="2fa-disable-password"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
                    >
                      <FaLock />
                    </span>
                    <Input
                      id="2fa-disable-password"
                      name="disablePassword"
                      type="password"
                      value={disablePassword}
                      onChange={(e) => {
                        setDisablePassword(e.target.value);
                        setError(null);
                      }}
                      placeholder="Enter your password"
                      disabled={isDisabling}
                      required
                      autoComplete="current-password"
                      className="pl-10"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="2fa-disable-otp"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    2FA Code
                  </label>
                  <div className="relative">
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
                    >
                      <FaShieldAlt />
                    </span>
                    <Input
                      id="2fa-disable-otp"
                      name="disableOtp"
                      type="text"
                      value={disableOtp}
                      onChange={(e) => {
                        const value = e.target.value
                          .replace(/\D/g, '')
                          .slice(0, 6);
                        setDisableOtp(value);
                        setError(null);
                      }}
                      placeholder="000000"
                      disabled={isDisabling}
                      required
                      maxLength={6}
                      className="pl-10"
                    />
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    Enter the 6-digit code from your authenticator app
                  </div>
                </div>
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
      </DialogContent>
    </Dialog>
  );
}

export default TwoFactorAuthDialog;
