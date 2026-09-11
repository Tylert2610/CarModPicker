import { vi } from 'vitest';
import type { AuthContextType } from '../../contexts/AuthContextDefinition';
import type { UserRead } from '../../types/Api';
import { mockUser } from '../mocks/api';

type MockAuthState = {
  [K in keyof AuthContextType]?: AuthContextType[K] | undefined;
};

export const mockUseAuth = vi.fn<() => MockAuthState>();

export const mockAdminUser: UserRead = { ...mockUser, is_admin: true };
export const mockSuperuserUser: UserRead = {
  ...mockUser,
  is_admin: true,
  is_superuser: true,
};
