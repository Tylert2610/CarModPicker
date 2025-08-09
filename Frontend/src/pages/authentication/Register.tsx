import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Input from '../../components/common/Input';
import ButtonStretch from '../../components/buttons/StretchButton';
import apiClient from '../../services/Api';
import type { UserCreate, UserRead } from '../../types/Api';
import AuthCard from '../../components/auth/AuthCard';
import { ErrorAlert } from '../../components/common/Alerts';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import useApiRequest from '../../hooks/UseApiRequest';
import AuthForm from '../../components/auth/AuthForm';

function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
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
    setApiError(null); // Clear previous errors

    if (password !== confirmPassword) {
      setApiError("Passwords don't match.");
      return;
    }

    if (!username.trim() || !email.trim() || !password.trim()) {
      setApiError('All fields are required.');
      return;
    }

    const payload: UserCreate = {
      username: username,
      email: email,
      password: password,
    };

    const result = await performRegistration(payload);

    if (result) {
      console.log('Registration successful:', result);
      navigate('/login'); // Redirect to login page after successful registration
    }
  };

  return (
    <AuthCard title="Create your account">
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
          label="Email address"
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          disabled={isLoading}
        />
        <Input
          label="Password"
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          disabled={isLoading}
        />
        <Input
          label="Confirm Password"
          id="confirm-password"
          name="confirm-password"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Confirm Password"
          disabled={isLoading}
        />

        <ErrorAlert message={apiError} />

        <div>
          <ButtonStretch type="submit" disabled={isLoading}>
            {isLoading ? 'Signing up...' : 'Sign up'}
          </ButtonStretch>
        </div>
      </AuthForm>
      <AuthRedirectLink
        text="Already have an account?"
        linkText="Sign in"
        to="/login"
      />
    </AuthCard>
  );
}
export default Register;
