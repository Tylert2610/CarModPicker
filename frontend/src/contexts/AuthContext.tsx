// filepath: src/contexts/AuthContext.tsx
import * as Sentry from '@sentry/react';
import type { ReactNode } from 'react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import {
  apiClient,
  isApiErrorWithStatus,
  removeStoredToken,
} from '../api/client';
import type { UserRead } from '../types/Api';
import { AuthContext } from './AuthContextDefinition';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<UserRead | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const navigate = useNavigate();

  const checkAuthStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get<UserRead>('/users/me');
      if (response.data) {
        setUser(response.data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      // Silently handle auth errors - user might not be logged in
      setUser(null);
      setIsAuthenticated(false);
      // The status only exists when the API answered. A network failure or a
      // timeout throws a different error class carrying none, which is why this
      // narrows rather than reaching for a status that may not be there.
      const status = isApiErrorWithStatus(error) ? error.status : undefined;
      // Clear invalid token on 401
      if (status === 401) {
        removeStoredToken();
      }
      // Don't log network errors in console to avoid noise
      // Only log unexpected errors
      if (status !== undefined && status !== 401) {
        console.error('Auth check failed:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void checkAuthStatus();
  }, [checkAuthStatus]);

  // D-40: bind Sentry user scope to current user. ONLY id — never email,
  // username, or name. Mirrors backend D-09 PII posture. The [user] dep
  // covers login, logout, and null transitions automatically.
  useEffect(() => {
    Sentry.setUser(user ? { id: String(user.id) } : null);
  }, [user]);

  const login = (userData: UserRead) => {
    setUser(userData);
    setIsAuthenticated(true);
  };

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } catch {
      // Clear token even if logout API call fails
      removeStoredToken();
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      void navigate('/'); // Redirect to login after logout
    }
  }, [navigate]);

  const contextValue = useMemo(
    () => ({
      isAuthenticated,
      user,
      login,
      logout,
      checkAuthStatus,
      isLoading,
    }),
    [isAuthenticated, user, logout, checkAuthStatus, isLoading]
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
};
