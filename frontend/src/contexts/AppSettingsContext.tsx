/**
 * Provider that loads global app settings once at mount and exposes a refresh.
 * A failed load leaves settings null so callers fall back to defaults.
 */

import type { ReactNode } from 'react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';

import type { AppSettings } from '../api/app_settings';
import { appSettingsApi } from '../api/app_settings';
import { AppSettingsContext } from './AppSettingsContextDefinition';

/** Loads global app settings once at mount and keeps them refreshable. */
export const AppSettingsProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await appSettingsApi.get();
      setSettings(response.data);
    } catch {
      setSettings(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ settings, isLoading, refresh, setSettings }),
    [settings, isLoading, refresh]
  );

  return (
    <AppSettingsContext.Provider value={value}>
      {children}
    </AppSettingsContext.Provider>
  );
};
