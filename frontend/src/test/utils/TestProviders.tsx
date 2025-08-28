import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { vi } from 'vitest';
import type { UserRead } from '../../types/Api';
import { mockUseAuth } from './test-mocks';

interface TestProvidersProps {
  children: React.ReactNode;
  initialAuthState?: {
    isAuthenticated: boolean;
    user?: UserRead | null;
    isLoading?: boolean;
  };
}



const defaultAuthState = { isAuthenticated: false, isLoading: false, user: null };

export const TestProviders: React.FC<TestProvidersProps> = ({
  children,
  initialAuthState = defaultAuthState,
}) => {
  // Set up the mock useAuth hook to return the initial state
  mockUseAuth.mockReturnValue({
    isAuthenticated: initialAuthState.isAuthenticated,
    user: initialAuthState.user,
    isLoading: initialAuthState.isLoading,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  });

  return <BrowserRouter>{children}</BrowserRouter>;
};


