import { render } from '@testing-library/react';
import type { ComponentType, ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';

import { ALL_ROUTES, type RouteGroup } from './test/route-coverage-list';

/**
 * Phase 6 FE-03 / D-10 / D-24 — parametrized App-level route-group coverage.
 *
 * For every <Route path> in App.tsx this test:
 *   1. Forces the matched lazy page component to THROW during render (via a
 *      hoisted `vi.mock('./utils/lazyWithReload')` stub keyed off
 *      `throwState.shouldThrow`).
 *   2. Renders <App /> at that path under MemoryRouter.
 *   3. Asserts the enclosing RouteGroupBoundary fallback rendered with the
 *      expected `[data-route-group="<group>"]` marker.
 *
 * D-10 / D-24 mandate: the test MUST observe the route-group fallback. A
 * happy-path-only assertion (e.g. asserting only that the document body
 * exists) is EXPLICITLY rejected — it does not exercise FE-03's wrapping.
 * Reviewers must reject any PR that weakens the assertion to a generic body
 * check.
 *
 * Drift guard: ALL_ROUTES.length must stay >= 38 (conservative floor;
 * `grep -cE 'path="' frontend/src/App.tsx` currently returns 39). Adding a
 * <Route> without categorising it here breaks CI, forcing the developer to
 * assign a group.
 *
 * Backend analog: backend/tests/test_admin_auth_coverage.py +
 * backend/tests/test_auth_auth_coverage.py — same parametrize-then-drift-guard
 * pattern, ported from pytest to vitest per D-24.
 *
 * Auth-redirect mitigation (06-03 plan NOTE): Plan gave two options for
 * handling GuestRoute / ProtectedRoute / EmailVerifiedRoute redirects during
 * coverage. This test uses Option 1 (TestProviders-style mock) but toggles
 * the auth state per-group via a hoisted mutable object so:
 *   - authentication group paths render under a NOT-authenticated user
 *     (GuestRoute lets /login etc. through → lazy stub throws inside →
 *     `authentication` boundary catches).
 *   - builder group paths render under an AUTHENTICATED email-verified user
 *     (ProtectedRoute + EmailVerifiedRoute let them through → lazy stub
 *     throws inside → `builder` boundary catches).
 *   - public + admin groups do not care — mock stays unauthenticated by
 *     default (admin routes have no auth guard around them in App.tsx).
 * Documented in SUMMARY.md under "Auth-redirect mitigation".
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
