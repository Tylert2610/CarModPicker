/**
 * Admin user management fixtures.
 */

import type { UserRead } from '../../../types/Api';

/** Builds a user fixture as the admin console sees it. */
export const makeAdminUserView = (
  overrides: Partial<UserRead> = {}
): UserRead => ({
  id: '11111111-1111-7111-8111-111111111111',
  username: 'adminuser',
  email: 'admin@example.com',
  disabled: false,
  email_verified: true,
  image_urls: ['https://example.com/admin.jpg'],
  is_superuser: false,
  is_admin: true,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'active',
  totp_enabled: false,
  ...overrides,
});

/** Builds a list of admin user fixtures. */
export const makeUserList = (items?: UserRead[]): UserRead[] =>
  items ?? [makeAdminUserView()];
