// App Settings domain API. Mirrors backend endpoints/app_settings.py.
//
// Co-located response types per D-04 (these are not pydantic-generated and
// only consumed via this domain module).
import { apiClient } from './client';

export interface AppSettings {
  /** Admin kill switch: when true, the entire premium system is disconnected
   *  (ads off, no feature gates, all premium UX/messaging hidden). */
  premium_disabled: boolean;
  updated_at: string;
}

export interface AppSettingsUpdate {
  premium_disabled?: boolean;
}

export const appSettingsApi = {
  /** Public: fetch global app settings (consumed by frontend to honor toggles). */
  get: () => apiClient.get<AppSettings>('/app-settings/'),
  /** Admin-only: update global app settings. */
  update: (body: AppSettingsUpdate) =>
    apiClient.put<AppSettings>('/app-settings/', body),
};
