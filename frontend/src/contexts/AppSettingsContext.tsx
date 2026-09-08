import type { ReactNode } from 'react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';

import type { AppSettings } from '../api/app_settings';
import { appSettingsApi } from '../api/app_settings';
import { AppSettingsContext } from './AppSettingsContextDefinition';

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
      // If the public settings endpoint is unreachable, default to "ads enabled" —
      // i.e. leave settings null so isPremium() is the only gate. Don't surface errors.
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
