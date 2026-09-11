/**
 * Tests for useAppSettings.
 */

import { createElement, type ReactNode } from 'react';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAppSettings } from './useAppSettings';
import {
  AppSettingsContext,
  type AppSettingsContextType,
} from '../contexts/AppSettingsContextDefinition';
import type { AppSettings } from '../api/app_settings';

function makeValue(
  overrides: Partial<AppSettingsContextType> = {}
): AppSettingsContextType {
  return {
    settings: null,
    isLoading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    setSettings: vi.fn(),
    ...overrides,
  };
}

const wrap = (value: AppSettingsContextType) => {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(AppSettingsContext.Provider, { value }, children);
  return Wrapper;
};

describe('useAppSettings', () => {
  it('returns the null-settings default when provider value is empty', () => {
    const value = makeValue();
    const { result } = renderHook(() => useAppSettings(), {
      wrapper: wrap(value),
    });

    expect(result.current.settings).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(typeof result.current.refresh).toBe('function');
    expect(typeof result.current.setSettings).toBe('function');
  });

  it('returns the loaded settings object when provider exposes one', () => {
    const settings: AppSettings = {
      premium_disabled: false,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const value = makeValue({ settings, isLoading: false });

    const { result } = renderHook(() => useAppSettings(), {
      wrapper: wrap(value),
    });

    expect(result.current.settings).toEqual(settings);
    expect(result.current.settings?.premium_disabled).toBe(false);
  });

  it('reflects isLoading=true while the provider is refreshing', () => {
    const value = makeValue({ isLoading: true });
    const { result } = renderHook(() => useAppSettings(), {
      wrapper: wrap(value),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.settings).toBeNull();
  });

  it('throws when used outside of an AppSettingsProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => renderHook(() => useAppSettings())).toThrow(
      /useAppSettings must be used within an AppSettingsProvider/
    );
    spy.mockRestore();
  });
});
