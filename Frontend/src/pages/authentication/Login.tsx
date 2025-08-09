import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Input from '../../components/common/Input';
import ButtonStretch from '../../components/buttons/StretchButton';
import apiClient from '../../services/Api';
import type { UserRead } from '../../types/Api'; 
import AuthCard from '../../components/auth/AuthCard';
import { ErrorAlert } from '../../components/common/Alerts';
import { useAuth } from '../../contexts/AuthContext';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import useApiRequest from '../../hooks/UseApiRequest';
import AuthForm from '../../components/auth/AuthForm';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
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
    setApiError(null); // Clear previous errors

    if (!username.trim() || !password.trim()) {
      setApiError('Username and password cannot be empty.');
      return;
    }

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const result = await performLogin(formData);

    if (result) {
      // Successfully logged in
      console.log('Login successful:', result);
      authLogin(result);
      navigate('/');
    }
    // If result is null, an API error occurred and apiError will be set by the hook
  };

  return (
    <AuthCard title="Sign in to your account">
      <AuthForm onSubmit={handleSubmit}>
        <Input
          label="Username"
          id="username"
          name="username"
          type="text"
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          disabled={isLoading}
        />
        <Input
          label="Password"
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          disabled={isLoading}
        />

        <ErrorAlert message={apiError} />

        <div className="flex items-center justify-between">
          <div className="text-sm">
            <Link
              to="/forgot-password"
              className="font-medium text-indigo-400 hover:text-indigo-300"
            >
              Forgot your password?
            </Link>
          </div>
        </div>

        <div>
          <ButtonStretch type="submit" disabled={isLoading}>
            {isLoading ? 'Signing in...' : 'Sign in'}
          </ButtonStretch>
        </div>
      </AuthForm>
      <AuthRedirectLink
        text="Don't have an account?"
        linkText="Sign up"
        to="/register"
      />
    </AuthCard>
  );
}
export default Login;
