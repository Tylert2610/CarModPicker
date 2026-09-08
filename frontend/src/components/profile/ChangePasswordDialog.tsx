import React, { useState } from 'react';
import { FaShieldAlt } from 'react-icons/fa';
import { useAuth } from '../../hooks/useAuth';
import { ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';

interface ChangePasswordDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onPasswordChanged: () => void;
  userId: string;
}

const ChangePasswordDialog: React.FC<ChangePasswordDialogProps> = ({
  isOpen,
  onClose,
  onPasswordChanged,
  userId,
}) => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: '',
    otp: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleClose = () => {
    setFormData({
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
      otp: '',
    });
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.currentPassword.trim()) {
      setError('Current password is required.');
      return;
    }

    if (!formData.newPassword.trim()) {
      setError('New password is required.');
      return;
    }

    if (formData.newPassword !== formData.confirmNewPassword) {
      setError("New passwords don't match.");
      return;
    }

    if (formData.newPassword.length < 8) {
      setError('New password must be at least 8 characters long.');
      return;
    }

    // If 2FA is enabled, require OTP
    if (user?.totp_enabled) {
      if (!formData.otp.trim() || formData.otp.length !== 6) {
        setError('2FA is enabled. Please enter a valid 6-digit OTP code.');
        return;
      }
    }

    setIsSubmitting(true);

    try {
      const { usersApi } = await import('../../api/users');
      const updateData: {
        current_password: string;
        password: string;
        otp?: string;
      } = {
        current_password: formData.currentPassword,
        password: formData.newPassword,
      };

      // Include OTP if 2FA is enabled
      if (user?.totp_enabled) {
        updateData.otp = formData.otp;
      }

      const response = await usersApi.updateUser(userId, updateData);

      if (response.data) {
        handleClose();
        onPasswordChanged();
      }
    } catch (err: unknown) {
      let errorMessage = 'Failed to change password';
      if (err instanceof Error) {
        errorMessage = err.message;
      } else if (typeof err === 'object' && err !== null && 'response' in err) {
        const response = (err as { response?: { data?: { detail?: string } } })
          .response;
        if (response?.data?.detail) {
          errorMessage = response.data.detail;
        }
      }
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Change Password</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
          {error && <ErrorAlert message={error} />}

          <div>
            <label
              htmlFor="currentPassword"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Current Password
            </label>
            <Input
              id="currentPassword"
              name="currentPassword"
              type="password"
              value={formData.currentPassword}
              onChange={handleInputChange}
              disabled={isSubmitting}
              required
              autoComplete="current-password"
            />
          </div>

          <div>
            <label
              htmlFor="newPassword"
              className="block text-sm font-medium text-foreground mb-2"
            >
              New Password
            </label>
            <Input
              id="newPassword"
              name="newPassword"
              type="password"
              value={formData.newPassword}
              onChange={handleInputChange}
              disabled={isSubmitting}
              required
              autoComplete="new-password"
              minLength={8}
            />
          </div>

          <div>
            <label
              htmlFor="confirmNewPassword"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Confirm New Password
            </label>
            <Input
              id="confirmNewPassword"
              name="confirmNewPassword"
              type="password"
              value={formData.confirmNewPassword}
              onChange={handleInputChange}
              disabled={isSubmitting}
              required
              autoComplete="new-password"
            />
          </div>

          {user?.totp_enabled && (
            <div>
              <label
                htmlFor="otp"
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
                  id="otp"
                  name="otp"
                  type="text"
                  value={formData.otp}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                    setFormData((prev) => ({ ...prev, otp: value }));
                    setError(null);
                  }}
                  placeholder="000000"
                  disabled={isSubmitting}
                  required
                  maxLength={6}
                  className="pl-10"
                />
              </div>
              <div className="mt-2 text-sm text-muted-foreground">
                Enter the 6-digit code from your authenticator app
              </div>
            </div>
          )}

          <div className="flex space-x-3 pt-4">
            <Button
              type="submit"
              disabled={isSubmitting}
              loading={isSubmitting}
              className="w-full"
            >
              {isSubmitting ? 'Changing Password...' : 'Change Password'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={handleClose}
              disabled={isSubmitting}
              className="w-full"
            >
              Cancel
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default ChangePasswordDialog;
