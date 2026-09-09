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
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { isGoogleConfigured } from '../../hooks/useGoogleSignIn';
import { authApi } from '../../api/auth';
import { getApiErrorMessage } from '../../utils/apiError';

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
  const [requires2FA, setRequires2FA] = useState(false);
  const [isPasskeyLoading, setIsPasskeyLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get('returnTo'));
  const { login: authLogin } = useAuth();
  const passkeySupported = browserSupportsWebAuthn();

  const loginRequestFn = (payload: URLSearchParams) =>
    authApi.login(payload as unknown as { username: string; password: string });

  const {
    error: apiError,
    isLoading,
    executeRequest: performLogin,
    setError: setApiError,
  } = useApiRequest(loginRequestFn);

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

    // If 2FA is required, handle OTP verification
    if (requires2FA) {
      if (!otp.trim() || otp.length !== 6) {
        setApiError('Please enter a valid 6-digit OTP code.');
        return;
      }

      try {
        const result = await authApi.loginWith2FA({
          username,
          password,
          otp,
        });
        if (result.data) {
          authLogin(result.data);
          void navigate(returnTo);
        }
      } catch (error: unknown) {
        setApiError(
          getApiErrorMessage(error, 'Invalid OTP code. Please try again.')
        );
      }
      return;
    }

    // Regular login
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const result = await performLogin(formData);
      // Check if result is a LoginResponse with requires_2fa
      if (result && 'requires_2fa' in result && result.requires_2fa) {
        setRequires2FA(true);
        setApiError(null);
      } else if (result && 'id' in result) {
        // Regular login success
        authLogin(result);
        void navigate(returnTo);
      }
    } catch {
      // Login failed - error is handled by useApiRequest
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
                ? 'Enter the 6-digit code from your authenticator app'
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
                        const value = e.target.value
                          .replace(/\D/g, '')
                          .slice(0, 6);
                        setOtp(value);
                      }}
                      placeholder="000000"
                      disabled={isLoading}
                      maxLength={6}
                      className="pl-10"
                    />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setRequires2FA(false);
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

            {!requires2FA && (passkeySupported || isGoogleConfigured()) && (
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
                <GoogleAuthFlow
                  onLoggedIn={(user) => {
                    authLogin(user);
                    void navigate(returnTo);
                  }}
                  onError={(message) => setApiError(message)}
                  disabled={isLoading || isPasskeyLoading}
                />
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
