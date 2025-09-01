import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Input from '../../components/common/Input';
import Button from '../../components/buttons/Button';
import apiClient from '../../services/Api';
import type { UserCreate, UserRead } from '../../types/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import { FaUser, FaEnvelope, FaLock, FaEye, FaEyeSlash } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import { Link } from 'react-router-dom';

function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const navigate = useNavigate();

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
        console.log('Registration successful:', result);
        void navigate('/login');
      }
    } catch (error) {
      console.error('Registration failed:', error);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl animate-float"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }}></div>
      </div>

      <div className="relative z-10 w-full max-w-md">
        <div className="glass-card rounded-2xl p-8 animate-slideInUp">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center shadow-lg">
                <GiRaceCar className="text-white text-2xl" />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-white mb-2">
              Join CarModPicker
            </h2>
            <p className="text-neutral-400">
              Create your account and start building
            </p>
          </div>

          {/* Form */}
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
            <Input
              label="Username"
              name="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Choose a username"
              disabled={isLoading}
              leftIcon={<FaUser />}
              variant="glass"
            />

            <Input
              label="Email address"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={isLoading}
              leftIcon={<FaEnvelope />}
              variant="glass"
            />

            <Input
              label="Password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create a password"
              disabled={isLoading}
              leftIcon={<FaLock />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-neutral-400 hover:text-white transition-colors"
                >
                  {showPassword ? <FaEyeSlash /> : <FaEye />}
                </button>
              }
              variant="glass"
              helperText="Must be at least 8 characters"
            />

            <Input
              label="Confirm Password"
              name="confirm-password"
              type={showConfirmPassword ? 'text' : 'password'}
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
              disabled={isLoading}
              leftIcon={<FaLock />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="text-neutral-400 hover:text-white transition-colors"
                >
                  {showConfirmPassword ? <FaEyeSlash /> : <FaEye />}
                </button>
              }
              variant="glass"
              error={password !== confirmPassword && confirmPassword ? "Passwords don't match" : undefined}
            />

            {apiError && (
              <div className="animate-slideInUp">
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                  <p className="text-red-400 text-sm">{apiError}</p>
                </div>
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
          </form>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-neutral-400 text-sm">
              Already have an account?{' '}
              <Link
                to="/login"
                className="text-primary-400 hover:text-primary-300 font-semibold transition-colors duration-300"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-8 text-center">
          <p className="text-neutral-500 text-xs">
            By creating an account, you agree to our{' '}
            <Link to="/privacy-policy" className="text-neutral-400 hover:text-white transition-colors">
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Register;
