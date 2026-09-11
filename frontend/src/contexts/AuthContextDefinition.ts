/**
 * Context object and type for the signed in user. Kept apart from the provider
 * so the provider file exports only components and stays refresh safe.
 */

import { createContext } from 'react';
import type { UserRead } from '../types/Api';

/** The signed in user plus the calls that change session state. */
export interface AuthContextType {
  isAuthenticated: boolean;
  user: UserRead | null;
  login: (userData: UserRead) => void;
  logout: () => void;
  checkAuthStatus: () => Promise<void>;
  isLoading: boolean;
}

/** Context carrying the current session to the tree. */
export const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);
