/**
 * Context object and type for global app settings. Kept apart from the provider
 * so the provider file exports only components and stays refresh safe.
 */

import { createContext } from 'react';
import type { AppSettings } from '../api/app_settings';

/** Global settings plus their loading state and a refresh. */
export interface AppSettingsContextType {
  settings: AppSettings | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  setSettings: (s: AppSettings) => void;
}

/** Context carrying global app settings to the tree. */
export const AppSettingsContext = createContext<
  AppSettingsContextType | undefined
>(undefined);
