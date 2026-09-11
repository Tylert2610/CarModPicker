import type { UserRead } from '../types/Api';

/**
 * True when the user holds an active, unexpired premium subscription. Gates ads
 * and premium features.
 */
export function isPremium(user: UserRead | null | undefined): boolean {
  if (!user) return false;
  if (user.subscription_tier !== 'premium') return false;
  if (user.subscription_status !== 'active') return false;
  const expiresAt = user.subscription_expires_at;
  if (expiresAt != null && new Date(expiresAt) <= new Date()) return false;
  return true;
}
