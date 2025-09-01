import React from 'react';
import { TestProviders } from './TestProviders';
import type { UserRead } from '../../types/Api';

interface CustomRenderOptions {
  route?: string;
  initialAuthState?: {
    isAuthenticated: boolean;
    user?: UserRead | null;
    isLoading?: boolean;
  };
}

const AllTheProviders = ({
  children,
  initialAuthState,
}: {
  children: React.ReactNode;
  initialAuthState?: CustomRenderOptions['initialAuthState'];
}) => {
  return (
    <TestProviders initialAuthState={initialAuthState}>
      {children}
    </TestProviders>
  );
};

export { AllTheProviders };
