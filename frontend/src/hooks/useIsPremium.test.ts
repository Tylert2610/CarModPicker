/**
 * Tests for useIsPremium.
 */

import { createElement, type ReactNode } from 'react';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useIsPremium, useIsPremiumSystemDisabled } from './useIsPremium';
import {
  AuthContext,
  type AuthContextType,
} from '../contexts/AuthContextDefinition';
import {
  AppSettingsContext,
  type AppSettingsContextType,
} from '../contexts/AppSettingsContextDefinition';
import type { AppSettings } from '../api/app_settings';
import type { UserRead } from '../types/Api';
import { mockUser } from '../test/mocks/api';
import { testScenarios } from '../test/utils/test-utils';

function authValue(
  scenario: (typeof testScenarios)[keyof typeof testScenarios],
  userOverride?: UserRead | null
): AuthContextType {
  const base = scenario.initialAuthState;
  return {
    isAuthenticated: base.isAuthenticated,
    user: userOverride !== undefined ? userOverride : null,
    isLoading: base.isLoading ?? false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  };
}

function settingsValue(settings: AppSettings | null): AppSettingsContextType {
  return {
    settings,
    isLoading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    setSettings: vi.fn(),
  };
}

const wrap = (auth: AuthContextType, settings: AppSettingsContextType) => {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(
      AuthContext.Provider,
      { value: auth },
      createElement(AppSettingsContext.Provider, { value: settings }, children)
    );
  return Wrapper;
};

const makePremiumUser = (overrides: Partial<UserRead> = {}): UserRead => ({
  ...mockUser,
  subscription_tier: 'premium',
  subscription_status: 'active',
  subscription_expires_at: null,
  ...overrides,
});

describe('useIsPremium', () => {
  it('returns false for an unauthenticated user', () => {
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        authValue(testScenarios.unauthenticated),
        settingsValue(null)
      ),
    });

    expect(result.current).toBe(false);
  });

  it("returns false for a user with subscription_tier='free'", () => {
    const freeUser: UserRead = {
      ...mockUser,
      subscription_tier: 'free',
      subscription_status: 'active',
    };
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        authValue(testScenarios.authenticated, freeUser),
        settingsValue(null)
      ),
    });

    expect(result.current).toBe(false);
  });

  it('returns true for an active premium user', () => {
    const premiumUser = makePremiumUser();
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        authValue(testScenarios.authenticated, premiumUser),
        settingsValue(null)
      ),
    });

    expect(result.current).toBe(true);
  });

  it('returns false for a premium user whose subscription has expired', () => {
    const expiredUser = makePremiumUser({
      subscription_expires_at: '2000-01-01T00:00:00Z',
    });
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        authValue(testScenarios.authenticated, expiredUser),
        settingsValue(null)
      ),
    });

    expect(result.current).toBe(false);
  });

  it('returns true for any user when admin kill-switch disables premium system', () => {
    const freeUser: UserRead = {
      ...mockUser,
      subscription_tier: 'free',
      subscription_status: 'active',
    };
    const killSwitch: AppSettings = {
      premium_disabled: true,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        authValue(testScenarios.authenticated, freeUser),
        settingsValue(killSwitch)
      ),
    });

    expect(result.current).toBe(true);
  });
});

describe('useIsPremiumSystemDisabled', () => {
  it('returns true when settings.premium_disabled is true', () => {
    const killSwitch: AppSettings = {
      premium_disabled: true,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const { result } = renderHook(() => useIsPremiumSystemDisabled(), {
      wrapper: wrap(
        authValue(testScenarios.unauthenticated),
        settingsValue(killSwitch)
      ),
    });

    expect(result.current).toBe(true);
  });

  it('returns false when settings are null or premium_disabled=false', () => {
    const { result: nullResult } = renderHook(
      () => useIsPremiumSystemDisabled(),
      {
        wrapper: wrap(
          authValue(testScenarios.unauthenticated),
          settingsValue(null)
        ),
      }
    );
    expect(nullResult.current).toBe(false);

    const enabled: AppSettings = {
      premium_disabled: false,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const { result: enabledResult } = renderHook(
      () => useIsPremiumSystemDisabled(),
      {
        wrapper: wrap(
          authValue(testScenarios.unauthenticated),
          settingsValue(enabled)
        ),
      }
    );
    expect(enabledResult.current).toBe(false);
  });
});
