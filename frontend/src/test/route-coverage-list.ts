/**
 * The App.tsx route enumeration, shared by the coverage test's drift guard and
 * the Playwright per-route screenshot loop. A new `<Route>` needs an entry here.
 */

export type RouteGroup = 'admin' | 'authentication' | 'builder' | 'public';

/** One route and the group it belongs to. */
export interface CoverageRoute {
  path: string;
  group: RouteGroup;
}

/** Every route in the app, kept in step with the App.tsx route table. */
export const ALL_ROUTES: ReadonlyArray<CoverageRoute> = [
  { path: '/', group: 'public' },
  { path: '/about', group: 'public' },
  { path: '/privacy-policy', group: 'public' },
  { path: '/terms-of-service', group: 'public' },
  { path: '/contact-us', group: 'public' },
  { path: '/support', group: 'public' },
  { path: '/pricing', group: 'public' },
  { path: '/bug-report', group: 'public' },
  { path: '/search', group: 'public' },
  { path: '/user/00000000-0000-0000-0000-000000000000', group: 'public' },
  { path: '/verify-email/confirm', group: 'public' },
  { path: '/forgot-password/confirm', group: 'public' },
  { path: '/extension-auth', group: 'public' },
  { path: '/car-generations/some-car', group: 'public' },
  {
    path: '/build-lists/00000000-0000-0000-0000-000000000000',
    group: 'public',
  },
  {
    path: '/build-lists/00000000-0000-0000-0000-000000000000/build-log',
    group: 'public',
  },
  { path: '/build-lists', group: 'public' },
  { path: '/parts/some-part/edit', group: 'public' },
  { path: '/parts/some-part', group: 'public' },
  { path: '/parts', group: 'public' },
  { path: '/_kitchen-sink', group: 'public' },
  { path: '/nonexistent-route-for-404-test', group: 'public' },

  { path: '/login', group: 'authentication' },
  { path: '/register', group: 'authentication' },
  { path: '/forgot-password', group: 'authentication' },

  { path: '/profile', group: 'builder' },
  { path: '/builder', group: 'builder' },
  { path: '/my-parts', group: 'builder' },
  { path: '/checkout', group: 'builder' },
  { path: '/verify-email', group: 'builder' },

  { path: '/admin', group: 'admin' },
  { path: '/admin/reports', group: 'admin' },
  { path: '/admin/bug-reports', group: 'admin' },
  { path: '/admin/users', group: 'admin' },
  { path: '/admin/crawler', group: 'admin' },
  { path: '/admin/system', group: 'admin' },
  { path: '/admin/statistics', group: 'admin' },
  { path: '/admin/parts-curation', group: 'admin' },
  { path: '/admin/extraction-health', group: 'admin' },
] as const;
