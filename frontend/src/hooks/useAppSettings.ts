/**
 * Accessor for the app settings context that fails loudly outside its provider.
 */

import { useContext } from 'react';
import {
  AppSettingsContext,
  type AppSettingsContextType,
} from '../contexts/AppSettingsContextDefinition';

/** Returns global app settings, throwing outside an AppSettingsProvider. */
export const useAppSettings = (): AppSettingsContextType => {
  const context = useContext(AppSettingsContext);
  if (context === undefined) {
    throw new Error(
      'useAppSettings must be used within an AppSettingsProvider'
    );
  }
  return context;
};
