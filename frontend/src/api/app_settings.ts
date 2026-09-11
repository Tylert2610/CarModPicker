/**
 * Global app settings, including the premium kill switch the frontend honors
 * before rendering any premium gate or ad slot.
 */

import { apiClient } from './client';

/** Global settings every client reads before rendering premium surfaces. */
export interface AppSettings {
  /** Admin kill switch: when true, the entire premium system is disconnected
   *  (ads off, no feature gates, all premium UX/messaging hidden). */
  premium_disabled: boolean;
  updated_at: string;
}

/** Editable global settings. */
export interface AppSettingsUpdate {
  premium_disabled?: boolean;
}

/** Reads global app settings and, for admins, updates them. */
export const appSettingsApi = {
  /** Public: fetch global app settings (consumed by frontend to honor toggles). */
  get: () => apiClient.get<AppSettings>('/app-settings/'),
  /** Admin-only: update global app settings. */
  update: (body: AppSettingsUpdate) =>
    apiClient.put<AppSettings>('/app-settings/', body),
};
