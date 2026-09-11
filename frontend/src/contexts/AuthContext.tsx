/**
 * Provider that establishes and tracks the session, in bearer or identity mode,
 * and exposes the current user to the tree.
 */

import * as Sentry from '@sentry/react';
import type { ReactNode } from 'react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  apiClient,
  isApiErrorWithStatus,
  removeStoredToken,
} from '../api/client';
import { AUTH_MODE } from '../api/authMode';
import { restoreSession, signOut } from '../api/identityAuth';
import type { UserRead } from '../types/Api';
import { AuthContext } from './AuthContextDefinition';

/** Establishes the session at mount and exposes the current user to the tree. */
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
      setUser(null);
      setIsAuthenticated(false);
      const status = isApiErrorWithStatus(error) ? error.status : undefined;
      if (status === 401) {
        removeStoredToken();
      }
      if (status !== undefined && status !== 401) {
        console.error('Auth check failed:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      const restored = await restoreSession();
      if (cancelled) return;
      if (restored === false && AUTH_MODE === 'identity') {
        setUser(null);
        setIsAuthenticated(false);
        setIsLoading(false);
        return;
      }
      await checkAuthStatus();
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [checkAuthStatus]);

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
      await signOut();
    } catch {
      removeStoredToken();
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      void navigate('/');
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
