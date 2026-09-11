import { createElement, type ReactNode } from 'react';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAuth } from './useAuth';
import {
  AuthContext,
  type AuthContextType,
} from '../contexts/AuthContextDefinition';
import { mockUser } from '../test/mocks/api';
import { testScenarios } from '../test/utils/test-utils';

function makeContextValue(
  scenario: (typeof testScenarios)[keyof typeof testScenarios]
): AuthContextType {
  const { initialAuthState } = scenario;
  return {
    isAuthenticated: initialAuthState.isAuthenticated,
    user: null,
    isLoading: initialAuthState.isLoading ?? false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  };
}

const wrap = (value: AuthContextType) => {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(AuthContext.Provider, { value }, children);
  return Wrapper;
};

describe('useAuth', () => {
  it('returns unauthenticated state with testScenarios.unauthenticated', () => {
    const value = makeContextValue(testScenarios.unauthenticated);
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns authenticated state with testScenarios.authenticated', () => {
    const base = makeContextValue(testScenarios.authenticated);
    const value: AuthContextType = { ...base, user: mockUser };
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isLoading).toBe(false);
  });

  it('returns isLoading=true with testScenarios.loading', () => {
    const value = makeContextValue(testScenarios.loading);
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('throws when used outside of an AuthProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow(
      /useAuth must be used within an AuthProvider/
    );
    spy.mockRestore();
  });

  it('exposes login/logout/checkAuthStatus callables from context', () => {
    const value = makeContextValue(testScenarios.authenticated);
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(typeof result.current.login).toBe('function');
    expect(typeof result.current.logout).toBe('function');
    expect(typeof result.current.checkAuthStatus).toBe('function');
  });
});
