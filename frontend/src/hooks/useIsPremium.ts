/**
 * Premium entitlement checks that also honor the admin kill switch.
 */

import { useAuth } from './useAuth';
import { useAppSettings } from './useAppSettings';
import { isPremium } from '../utils/subscription';

/**
 * Returns true if the current user has an active premium subscription, OR if
 * the admin kill switch has disabled the premium system entirely (in which
 * case every user is treated as premium so all paid-tier gates fall away).
 */
export function useIsPremium(): boolean {
  const { user } = useAuth();
  const { settings } = useAppSettings();
  if (settings?.premium_disabled) return true;
  return isPremium(user);
}

/**
 * Returns true when the admin kill switch has disconnected the premium system.
 * Pricing pages, checkout, upgrade prompts, and any premium-only messaging
 * should be hidden when this is true.
 */
export function useIsPremiumSystemDisabled(): boolean {
  const { settings } = useAppSettings();
  return Boolean(settings?.premium_disabled);
}
