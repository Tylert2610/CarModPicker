import { createContext } from 'react';
import type { AppSettings } from '../api/app_settings';

export interface AppSettingsContextType {
  settings: AppSettings | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  setSettings: (s: AppSettings) => void;
}

export const AppSettingsContext = createContext<
  AppSettingsContextType | undefined
>(undefined);
