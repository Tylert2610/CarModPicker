// filepath: src/contexts/AuthContextDefinition.ts
import { createContext } from 'react';
import type { UserRead } from '../types/Api';

export interface AuthContextType {
  isAuthenticated: boolean;
  user: UserRead | null;
  login: (userData: UserRead) => void;
  logout: () => void;
  checkAuthStatus: () => Promise<void>;
  isLoading: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
