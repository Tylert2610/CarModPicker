/**
 * Shared auth mocks and the user variants the tests assert roles against.
 */

import { vi } from 'vitest';
import type { AuthContextType } from '../../contexts/AuthContextDefinition';
import type { UserRead } from '../../types/Api';
import { mockUser } from '../mocks/api';

type MockAuthState = {
  [K in keyof AuthContextType]?: AuthContextType[K] | undefined;
};

/** Mock for the useAuth hook, so tests can set the session directly. */
export const mockUseAuth = vi.fn<() => MockAuthState>();

/** User fixture carrying admin rights. */
export const mockAdminUser: UserRead = { ...mockUser, is_admin: true };
/** User fixture carrying superuser rights. */
export const mockSuperuserUser: UserRead = {
  ...mockUser,
  is_admin: true,
  is_superuser: true,
};
