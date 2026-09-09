import { useEffect, useState } from 'react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import { FaEye, FaEyeSlash, FaLock, FaShieldAlt, FaUser } from 'react-icons/fa';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import {
  isGoogleConfigured,
  useGoogleSignIn,
} from '../../hooks/useGoogleSignIn';
import { authApi } from '../../api/auth';
import type { UserRead } from '../../types/Api';
import { getApiErrorMessage } from '../../utils/apiError';

interface GoogleAuthFlowProps {
  onLoggedIn: (user: UserRead) => void;
  onError: (message: string) => void;
  disabled?: boolean;
}

const GoogleAuthFlow: React.FC<GoogleAuthFlowProps> = ({
  onLoggedIn,
  onError,
  disabled,
}) => {
  const { state, nonce, submitCredential, reset } = useGoogleSignIn({
    onLoggedIn,
    onError,
  });

  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [otp, setOtp] = useState('');
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const openLink = state.kind === 'link';
  const openSignup = state.kind === 'signup';
  const open2FA = state.kind === 'twoFactor';

  // Pre-fill the username field when the signup dialog first opens. Resetting back
  // to '' on close prevents a stale value bleeding into a later dialog.
  useEffect(() => {
    if (state.kind === 'signup') {
      setUsername(state.payload.suggested_username);
    } else {
      setUsername('');
    }
  }, [state]);

  if (!isGoogleConfigured()) return null;

  const closeDialog = () => {
    setPassword('');
    setOtp('');
    setUsername('');
    reset();
  };

  const handleCredential = (resp: CredentialResponse) => {
    if (!resp.credential) {
      onError('Google did not return a credential. Please try again.');
      return;
    }
    void submitCredential(resp.credential);
  };

  const handleLinkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'link') return;
    setSubmitting(true);
    try {
      const result = await authApi.googleLink({
        link_token: state.payload.link_token,
        password,
        ...(state.payload.has_totp ? { otp } : {}),
      });
      onLoggedIn(result.data);
      closeDialog();
    } catch (err) {
      onError(getApiErrorMessage(err, 'Linking failed. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'signup') return;
    setSubmitting(true);
    try {
      const result = await authApi.googleSignup({
        signup_token: state.payload.signup_token,
        username: username.trim(),
      });
      onLoggedIn(result.data);
      closeDialog();
    } catch (err) {
      onError(getApiErrorMessage(err, 'Could not finish account creation.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handle2FASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'twoFactor') return;
    setSubmitting(true);
    try {
      const result = await authApi.oauthTwoFactor({
        otp_token: state.payload.otp_token,
        otp,
      });
      onLoggedIn(result.data);
      closeDialog();
    } catch (err) {
      onError(getApiErrorMessage(err, 'Invalid code. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        className={`flex justify-center ${disabled ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <GoogleLogin
          onSuccess={handleCredential}
          onError={() => onError('Google sign-in was cancelled or failed.')}
          nonce={nonce}
          theme="filled_black"
          shape="pill"
          text="continue_with"
          width="320"
          useOneTap={false}
        />
      </div>

      <Dialog
        open={openLink}
        onOpenChange={(open) => {
          if (!open) closeDialog();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Link Google to your account</DialogTitle>
          </DialogHeader>
          {state.kind === 'link' && (
            <form
              onSubmit={(e) => void handleLinkSubmit(e)}
              className="space-y-5"
            >
              <p className="text-foreground text-sm">
                An account already exists for{' '}
                <span className="text-white font-medium">
                  {state.payload.email}
                </span>
                . Enter your password to merge Google sign-in into it.
              </p>
              <div>
                <label
                  htmlFor="google-link-password"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Password
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    <FaLock />
                  </span>
                  <Input
                    id="google-link-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white transition-colors"
                  >
                    {showPassword ? <FaEyeSlash /> : <FaEye />}
                  </button>
                </div>
              </div>
              {state.payload.has_totp && (
                <div>
                  <label
                    htmlFor="google-link-otp"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Authentication code
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                      <FaShieldAlt />
                    </span>
                    <Input
                      id="google-link-otp"
                      name="otp"
                      type="text"
                      required
                      value={otp}
                      onChange={(e) =>
                        setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))
                      }
                      placeholder="000000"
                      maxLength={6}
                      className="pl-10"
                    />
                  </div>
                </div>
              )}
              <Button
                type="submit"
                loading={submitting}
                disabled={submitting || !password}
                className="w-full"
                size="lg"
              >
                Link &amp; sign in
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={openSignup}
        onOpenChange={(open) => {
          if (!open) closeDialog();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Choose your username</DialogTitle>
          </DialogHeader>
          {state.kind === 'signup' && (
            <form
              onSubmit={(e) => void handleSignupSubmit(e)}
              className="space-y-5"
            >
              <p className="text-foreground text-sm">
                Welcome! Pick a username to finish creating your account for{' '}
                <span className="text-white font-medium">
                  {state.payload.email}
                </span>
                .
              </p>
              <div>
                <label
                  htmlFor="google-signup-username"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Username
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    <FaUser />
                  </span>
                  <Input
                    id="google-signup-username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              <Button
                type="submit"
                loading={submitting}
                disabled={submitting || !username.trim()}
                className="w-full"
                size="lg"
              >
                Create account
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={open2FA}
        onOpenChange={(open) => {
          if (!open) closeDialog();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Two-factor authentication</DialogTitle>
          </DialogHeader>
          {state.kind === 'twoFactor' && (
            <form
              onSubmit={(e) => void handle2FASubmit(e)}
              className="space-y-5"
            >
              <p className="text-foreground text-sm">
                Enter the 6-digit code from your authenticator app to complete
                sign-in.
              </p>
              <div>
                <label
                  htmlFor="google-2fa-otp"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  Authentication code
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    <FaShieldAlt />
                  </span>
                  <Input
                    id="google-2fa-otp"
                    name="otp"
                    type="text"
                    required
                    value={otp}
                    onChange={(e) =>
                      setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))
                    }
                    placeholder="000000"
                    maxLength={6}
                    className="pl-10"
                  />
                </div>
              </div>
              <Button
                type="submit"
                loading={submitting}
                disabled={submitting || otp.length !== 6}
                className="w-full"
                size="lg"
              >
                Verify
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default GoogleAuthFlow;
