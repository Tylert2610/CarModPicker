/**
 * Accessor for the auth context that fails loudly outside its provider.
 */

import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContextDefinition';

/** Returns the current session, throwing outside an AuthProvider. */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
