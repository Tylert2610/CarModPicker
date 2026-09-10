import React, { useState } from 'react';
import { FaEnvelope, FaEye, FaEyeSlash, FaLock, FaUser } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link, useNavigate } from 'react-router-dom';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import GoogleAuthFlow from '../../components/authentication/GoogleAuthFlow';
import { Input } from '../../components/ui/input';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { isGoogleConfigured } from '../../hooks/useGoogleSignIn';
import { identityAvailability } from '../../api/authMode';
import { apiClient } from '../../api/client';
import type { UserCreate, UserRead } from '../../types/Api';

function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const navigate = useNavigate();
  const { login: authLogin } = useAuth();

  const registerRequestFn = (payload: UserCreate) =>
    apiClient.post<UserRead>('/users/', payload);

  const {
    error: apiError,
    isLoading,
    executeRequest: performRegistration,
    setError: setApiError,
  } = useApiRequest(registerRequestFn);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (password !== confirmPassword) {
      setApiError("Passwords don't match.");
      return;
    }

    if (!username.trim() || !email.trim() || !password.trim()) {
      setApiError('All fields are required.');
      return;
    }

    if (password.length < 8) {
      setApiError('Password must be at least 8 characters long.');
      return;
    }

    const payload: UserCreate = {
      username: username,
      email: email,
      password: password,
    };

    try {
      const result = await performRegistration(payload);
      if (result) {
        void navigate('/login');
      }
    } catch {
      // Registration failed
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
              Join CarModPicker
            </h2>
            <p className="text-muted-foreground">
              Create your account and start building
            </p>
          </div>

          {/* Form */}
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
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
                  placeholder="Choose a username"
                  disabled={isLoading}
                  className="pl-10"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Email address
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  <FaEnvelope />
                </span>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
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
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
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
              <div className="mt-2 text-sm text-muted-foreground">
                Must be at least 8 characters
              </div>
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Confirm Password
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  <FaLock />
                </span>
                <Input
                  id="confirm-password"
                  name="confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  disabled={isLoading}
                  aria-invalid={
                    password !== confirmPassword && !!confirmPassword
                  }
                  className="pl-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white transition-colors"
                >
                  {showConfirmPassword ? <FaEyeSlash /> : <FaEye />}
                </button>
              </div>
              {password !== confirmPassword && confirmPassword && (
                <div className="mt-2 text-sm text-destructive">
                  Passwords don't match
                </div>
              )}
            </div>

            {apiError && (
              <div className="animate-slideInUp">
                <Alert variant="destructive">
                  <AlertDescription>{apiError}</AlertDescription>
                </Alert>
              </div>
            )}

            <Button
              type="submit"
              loading={isLoading}
              disabled={isLoading}
              className="w-full"
              size="lg"
            >
              {isLoading ? 'Creating account...' : 'Create account'}
            </Button>

            {/* Google sign in is M6 in the identity service and is not
                shipped, so identity mode hides it rather than rendering a
                button that 404s. Unchanged in bearer mode. */}
            {isGoogleConfigured() && identityAvailability().googleOauth && (
              <>
                <div className="flex items-center gap-3 my-2">
                  <div className="h-px flex-1 bg-muted"></div>
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">
                    or
                  </span>
                  <div className="h-px flex-1 bg-muted"></div>
                </div>
                <GoogleAuthFlow
                  onLoggedIn={(user) => {
                    authLogin(user);
                    void navigate('/');
                  }}
                  onError={(message) => setApiError(message)}
                  disabled={isLoading}
                />
              </>
            )}
          </form>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-muted-foreground text-sm">
              Already have an account?{' '}
              <Link
                to="/login"
                className="text-primary hover:text-primary/90 font-semibold transition-colors duration-300"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-8 text-center">
          <p className="text-muted-foreground text-xs">
            By creating an account, you agree to our{' '}
            <Link
              to="/terms-of-service"
              className="text-muted-foreground hover:text-white transition-colors"
            >
              Terms of Service
            </Link>{' '}
            and{' '}
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

export default Register;
