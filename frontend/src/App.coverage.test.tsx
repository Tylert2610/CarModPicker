import { render } from '@testing-library/react';
import type { ComponentType, ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';

import { ALL_ROUTES, type RouteGroup } from './test/route-coverage-list';

/**
 * Asserts every `<Route>` in App.tsx sits inside a route-group error boundary,
 * by forcing each lazy page to throw and checking the matching fallback
 * renders. A floor on the route count catches a route added without a group.
 */

class ResizeObserverStub {
  constructor(_cb: ResizeObserverCallback) {
    void _cb;
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

const { throwState, authState } = vi.hoisted(() => ({
  throwState: { shouldThrow: true },
  authState: { isAuthenticated: false, emailVerified: true },
}));

vi.mock('./utils/lazyWithReload', () => {
  const ThrowingStub: ComponentType<unknown> = () => {
    if (throwState.shouldThrow) {
      throw new Error('coverage-test-forced-throw');
    }
    return null;
  };
  return {
    lazyWithReload: () => ThrowingStub,
  };
});

vi.mock('./hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: authState.isAuthenticated,
    isLoading: false,
    user: authState.isAuthenticated
      ? {
          id: '00000000-0000-0000-0000-000000000001',
          username: 'covtest',
          email: 'covtest@example.com',
          email_verified: authState.emailVerified,
          disabled: false,
          is_admin: true,
          is_superuser: false,
          image_urls: [],
          subscription_tier: 'free',
        }
      : null,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  }),
}));

vi.mock('./hooks/useAppSettings', () => ({
  useAppSettings: () => ({
    settings: { premium_disabled: false },
    isLoading: false,
    refresh: vi.fn(),
    setSettings: vi.fn(),
  }),
}));

import App from './App';

/**
 * Select the auth state that lets a given group's routes actually mount
 * (rather than being redirected away by GuestRoute/ProtectedRoute/
 * EmailVerifiedRoute before the throwing stub gets a chance to run).
 */
function authForGroup(group: RouteGroup): {
  isAuthenticated: boolean;
  emailVerified: boolean;
} {
  switch (group) {
    case 'authentication':
      return { isAuthenticated: false, emailVerified: true };
    case 'builder':
      return { isAuthenticated: true, emailVerified: true };
    case 'admin':
    case 'public':
    default:
      return { isAuthenticated: false, emailVerified: true };
  }
}

describe('App route coverage (FE-03 drift guard, D-10, D-24)', () => {
  let errorSpy: MockInstance<typeof console.error>;
  let warnSpy: MockInstance<typeof console.warn>;

  beforeEach(() => {
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    throwState.shouldThrow = true;
  });

  afterEach(() => {
    errorSpy.mockRestore();
    warnSpy.mockRestore();
  });

  it('ALL_ROUTES enumerates at least the current Route count (drift guard)', () => {
    expect(ALL_ROUTES.length).toBeGreaterThanOrEqual(38);
  });

  describe.each(ALL_ROUTES)(
    'path=$path group=$group',
    ({ path, group }: { path: string; group: RouteGroup }) => {
      it(`forces child throw; route-group boundary renders fallback with data-route-group="${group}"`, () => {
        const { isAuthenticated, emailVerified } = authForGroup(group);
        authState.isAuthenticated = isAuthenticated;
        authState.emailVerified = emailVerified;

        const { container } = render(
          (
            <MemoryRouter initialEntries={[path]}>
              <App />
            </MemoryRouter>
          ) as ReactNode
        );
        const fallbackMarker = container.querySelector(
          `[data-route-group="${group}"]`
        );
        expect(
          fallbackMarker,
          `Expected fallback [data-route-group="${group}"] for path=${path}`
        ).not.toBeNull();
      });
    }
  );
});
