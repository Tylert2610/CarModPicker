import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Input from '../../components/common/Input';
import Button from '../../components/buttons/Button';
import apiClient from '../../services/Api';
import type { UserRead } from '../../types/Api'; 
import { useAuth } from '../../hooks/useAuth';
import useApiRequest from '../../hooks/UseApiRequest';
import { FaUser, FaLock, FaEye, FaEyeSlash } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const { login: authLogin } = useAuth();

  const loginRequestFn = (payload: URLSearchParams) =>
    apiClient.post<UserRead>('/auth/token', payload, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

  const {
    error: apiError,
    isLoading,
    executeRequest: performLogin,
    setError: setApiError,
  } = useApiRequest(loginRequestFn);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (!username.trim() || !password.trim()) {
      setApiError('Username and password cannot be empty.');
      return;
    }

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const result = await performLogin(formData);
      if (result) {
        console.log('Login successful:', result);
        authLogin(result);
        void navigate('/');
      }
    } catch (error) {
      console.error('Login failed:', error);
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
              Welcome Back
            </h2>
            <p className="text-neutral-400">
              Sign in to your CarModPicker account
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
              placeholder="Enter your username"
              disabled={isLoading}
              leftIcon={<FaUser />}
              variant="glass"
            />

            <Input
              label="Password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
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
            />

            {apiError && (
              <div className="animate-slideInUp">
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                  <p className="text-red-400 text-sm">{apiError}</p>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Link
                to="/forgot-password"
                className="text-sm text-primary-400 hover:text-primary-300 transition-colors duration-300"
              >
                Forgot your password?
              </Link>
            </div>

            <Button
              type="submit"
              loading={isLoading}
              disabled={isLoading}
              className="w-full"
              size="lg"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-neutral-400 text-sm">
              Don't have an account?{' '}
              <Link
                to="/register"
                className="text-primary-400 hover:text-primary-300 font-semibold transition-colors duration-300"
              >
                Sign up
              </Link>
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-8 text-center">
          <p className="text-neutral-500 text-xs">
            By signing in, you agree to our{' '}
            <Link to="/privacy-policy" className="text-neutral-400 hover:text-white transition-colors">
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
