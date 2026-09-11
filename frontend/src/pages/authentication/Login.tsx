import React, { useState } from 'react';
import {
  FaEye,
  FaEyeSlash,
  FaKey,
  FaLock,
  FaShieldAlt,
  FaUser,
} from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  browserSupportsWebAuthn,
  startAuthentication,
} from '@simplewebauthn/browser';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import GoogleAuthFlow from '../../components/authentication/GoogleAuthFlow';
import { Input } from '../../components/ui/input';
import { useAuth } from '../../hooks/useAuth';
import { isGoogleConfigured } from '../../hooks/useGoogleSignIn';
import { AUTH_MODE, identityAvailability } from '../../api/authMode';
import { authApi } from '../../api/auth';
import OAuthProviderButtons from '../../components/authentication/OAuthProviderButtons';
import PasskeySignInButton from '../../components/authentication/PasskeySignInButton';
import { useOAuthCallback } from '../../hooks/useOAuthCallback';
import { describeOAuthCallbackError } from '../../api/identityOAuth';
import type { PasskeySignInResult } from '../../api/identityPasskeys';
import { getApiErrorMessage } from '../../utils/apiError';
import type { UserRead } from '../../types/Api';
import {
  acceptsRecoveryCodes,
  completeMfa,
  signIn,
  type LoginChallenge,
} from '../../api/identityAuth';

/**
 * Only accept returnTo values that look like a local path. Blocks protocol-
 * relative and absolute URLs so a crafted /login?returnTo=... link can't be
 * used as an open-redirect gadget.
 */
const safeReturnTo = (value: string | null): string => {
  if (!value) return '/';
  if (!value.startsWith('/') || value.startsWith('//')) return '/';
  return value;
};

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  // The challenge from the first leg, or null when there is no challenge in
  // flight. Replaces the boolean this used to hold: in identity mode the second
  // leg needs the server's ticket, and in bearer mode it needs the credentials
  // again, so "a second factor is required" and "here is what it needs" are one
  // fact rather than two.
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null);
  const [isPasskeyLoading, setIsPasskeyLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get('returnTo'));
  const { login: authLogin, checkAuthStatus } = useAuth();
  // Both mechanisms carry passkeys and OAuth, and they carry them differently:
  // the legacy ones speak CarModPicker's own routes through
  // `@simplewebauthn/browser` and `@react-oauth/google`, the identity ones go
  // through the package. `available` says the mode has the affordance at all;
  // the identity components ask the deployment whether it is actually on and
  // render nothing when it is not.
  const available = identityAvailability();
  const identityMode = AUTH_MODE === 'identity';
  const passkeySupported =
    !identityMode && browserSupportsWebAuthn() && available.passkeys;
  const googleAvailable =
    !identityMode && isGoogleConfigured() && available.googleOauth;
  const requires2FA = challenge !== null;
  // Only the identity service issues recovery codes, and one is not six digits,
  // so the field stops being numeric when they are accepted.
  const allowRecoveryCode = acceptsRecoveryCodes();

  const [apiError, setApiError] = useState<string | null>(null);
  const isLoading = isSubmitting;

  /**
   * Finishes a sign in that has already succeeded on the server.
   *
   * Bearer login answers with the user in the body, so it is handed straight
   * to the context. Identity login answers with a token and no user, because
   * this application reads roughly twenty `UserRead` fields that no token claim
   * carries, so the user is fetched. One function rather than two so the
   * navigate happens in one place either way.
   */
  const finishLogin = async (user: UserRead | null) => {
    if (user !== null) {
      authLogin(user);
    } else {
      await checkAuthStatus();
    }
    void navigate(returnTo);
  };

  /**
   * Acts on an OAuth callback this page was reached from.
   *
   * Four markers, three of which are already modelled by the password flow's
   * own states: a completed sign in finishes exactly like a password one, an
   * MFA ticket becomes the same challenge the second leg reads, and a refusal
   * becomes the same banner. `linked` cannot reach the login page (it is a
   * callback for a signed in user), so it is folded into the sign in case.
   */
  useOAuthCallback(async (result) => {
    if (result.kind === 'signed-in' || result.kind === 'linked') {
      await finishLogin(null);
      return;
    }
    if (result.kind === 'mfa-required') {
      setChallenge({
        kind: 'identity-ticket',
        ticket: result.ticket,
        factors: [],
      });
      return;
    }
    setApiError(
      describeOAuthCallbackError(result, 'That sign in could not be completed.')
    );
  });

  /** Finishes a passwordless sign in, or shows why it did not finish. */
  const handlePasskeyResult = async (result: PasskeySignInResult) => {
    if (result.status === 'authenticated') {
      await finishLogin(null);
      return;
    }
    if (result.status === 'mfa-required') {
      setChallenge({
        kind: 'identity-ticket',
        ticket: result.ticket,
        factors: result.factors,
      });
      setApiError(null);
      return;
    }
    if (result.status === 'failed') setApiError(result.error);
  };

  const handlePasskeyLogin = async () => {
    setApiError(null);
    setIsPasskeyLoading(true);
    try {
      const optsResp = await authApi.webauthnLoginOptions(
        username.trim() || undefined
      );
      const { options, challenge_token } = optsResp.data;
      const credential = await startAuthentication({
        optionsJSON: options as unknown as Parameters<
          typeof startAuthentication
        >[0]['optionsJSON'],
      });
      const result = await authApi.webauthnLoginVerify({
        challenge_token,
        credential,
      });
      if (result.data) {
        authLogin(result.data);
        void navigate(returnTo);
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'NotAllowedError') {
        setApiError('Passkey sign-in was cancelled.');
      } else {
        setApiError(getApiErrorMessage(err, 'Passkey sign-in failed.'));
      }
    } finally {
      setIsPasskeyLoading(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (!username.trim() || !password.trim()) {
      setApiError('Username and password cannot be empty.');
      return;
    }

    // Second leg. The code is whatever the mode accepts: six digits always,
    // and a recovery code too when the identity service is the one checking.
    if (challenge !== null) {
      const code = otp.trim();
      if (code === '') {
        setApiError(
          allowRecoveryCode
            ? 'Enter your 6-digit code or a recovery code.'
            : 'Please enter a valid 6-digit OTP code.'
        );
        return;
      }
      if (!allowRecoveryCode && code.length !== 6) {
        setApiError('Please enter a valid 6-digit OTP code.');
        return;
      }

      setIsSubmitting(true);
      try {
        const result = await completeMfa(challenge, code);
        if (result.status === 'authenticated') {
          await finishLogin(result.user);
        } else if (result.status === 'failed') {
          setApiError(result.error);
        }
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    // First leg.
    setIsSubmitting(true);
    try {
      const result = await signIn(username, password);
      if (result.status === 'authenticated') {
        await finishLogin(result.user);
      } else if (result.status === 'mfa-required') {
        setChallenge(result.challenge);
        setApiError(null);
      } else {
        setApiError(result.error);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary/10 rounded-full blur-3xl animate-float"></div>
        <div
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl animate-float"
          style={{ animationDelay: '1s' }}
        ></div>
      </div>

      <div className="relative z-10 w-full max-w-md">
        <div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center shadow-lg">
                <GiRaceCar className="text-primary-foreground text-2xl" />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-white mb-2">
              {requires2FA ? 'Two-Factor Authentication' : 'Welcome Back'}
            </h2>
            <p className="text-muted-foreground">
              {requires2FA
                ? allowRecoveryCode
                  ? 'Enter the 6-digit code from your authenticator app, or one of your recovery codes'
                  : 'Enter the 6-digit code from your authenticator app'
                : 'Sign in to your CarModPicker account'}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
            {!requires2FA ? (
              <>
                <div>
                  <label
                    htmlFor="username"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Username
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                      <FaUser />
                    </span>
                    <Input
                      id="username"
                      name="username"
                      type="text"
                      autoComplete="username"
                      required
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Enter your username"
                      disabled={isLoading}
                      className="pl-10"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="password"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                      <FaLock />
                    </span>
                    <Input
                      id="password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      disabled={isLoading}
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
              </>
            ) : (
              <>
                <div className="flex justify-center mb-4">
                  <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center">
                    <FaShieldAlt className="text-primary text-3xl" />
                  </div>
                </div>
                <div>
                  <label
                    htmlFor="otp"
                    className="block text-sm font-medium text-foreground mb-2"
                  >
                    Authentication Code
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                      <FaShieldAlt />
                    </span>
                    <Input
                      id="otp"
                      name="otp"
                      type="text"
                      autoComplete="one-time-code"
                      required
                      value={otp}
                      onChange={(e) => {
                        // A recovery code is not six digits, so stripping
                        // non-digits would make it impossible to type. The
                        // server tells the two apart by shape.
                        const raw = e.target.value;
                        setOtp(
                          allowRecoveryCode
                            ? raw.slice(0, 32)
                            : raw.replace(/\D/g, '').slice(0, 6)
                        );
                      }}
                      placeholder={allowRecoveryCode ? 'Code' : '000000'}
                      disabled={isLoading}
                      maxLength={allowRecoveryCode ? 32 : 6}
                      inputMode={allowRecoveryCode ? 'text' : 'numeric'}
                      className="pl-10"
                    />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setChallenge(null);
                    setOtp('');
                    setApiError(null);
                  }}
                  className="text-sm text-primary hover:text-primary/90 transition-colors duration-300 w-full text-center"
                >
                  ← Back to login
                </button>
              </>
            )}

            {apiError && (
              <div className="animate-slideInUp">
                <Alert variant="destructive">
                  <AlertDescription>{apiError}</AlertDescription>
                </Alert>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Link
                to="/forgot-password"
                className="text-sm text-primary hover:text-primary/90 transition-colors duration-300"
              >
                Forgot your password?
              </Link>
            </div>

            <Button
              type="submit"
              loading={isLoading}
              disabled={isLoading || isPasskeyLoading}
              className="w-full"
              size="lg"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>

            {!requires2FA && identityMode && (
              <>
                <div className="flex items-center gap-3 my-2">
                  <div className="h-px flex-1 bg-muted"></div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">
                    or
                  </span>
                  <div className="h-px flex-1 bg-muted"></div>
                </div>
                <PasskeySignInButton
                  username={username}
                  onResult={(result) => void handlePasskeyResult(result)}
                  disabled={isLoading}
                />
                <OAuthProviderButtons
                  returnTo={returnTo}
                  disabled={isLoading}
                />
              </>
            )}

            {!requires2FA && (passkeySupported || googleAvailable) && (
              <>
                <div className="flex items-center gap-3 my-2">
                  <div className="h-px flex-1 bg-muted"></div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">
                    or
                  </span>
                  <div className="h-px flex-1 bg-muted"></div>
                </div>
                {passkeySupported && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="lg"
                    className="w-full"
                    onClick={() => void handlePasskeyLogin()}
                    disabled={isLoading || isPasskeyLoading}
                  >
                    <FaKey />
                    <span>
                      {isPasskeyLoading
                        ? 'Waiting for your passkey…'
                        : 'Sign in with a passkey'}
                    </span>
                  </Button>
                )}
                {googleAvailable && (
                  <GoogleAuthFlow
                    onLoggedIn={(user) => {
                      authLogin(user);
                      void navigate(returnTo);
                    }}
                    onError={(message) => setApiError(message)}
                    disabled={isLoading || isPasskeyLoading}
                  />
                )}
              </>
            )}
          </form>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-muted-foreground text-sm">
              Don't have an account?{' '}
              <Link
                to="/register"
                className="text-primary hover:text-primary/90 font-semibold transition-colors duration-300"
              >
                Sign up
              </Link>
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-8 text-center">
          <p className="text-muted-foreground text-xs">
            By signing in, you agree to our{' '}
            <Link
              to="/privacy-policy"
              className="text-muted-foreground hover:text-white transition-colors"
            >
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
