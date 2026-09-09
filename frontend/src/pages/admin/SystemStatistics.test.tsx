// Phase 8 plan 08-15 (D-02 Wave 4) — SystemStatistics page coverage.
//
// SystemStatistics.tsx (755 lines) is the primary admin stats dashboard.
// On mount it calls `fetchCounts()` which fires 15 count endpoints in parallel
// (users / cars / makes / car-models / build-lists / parts / categories /
// part-manufacturers / retailers / admin table-counts / build-log-posts /
// build-list-parts / votes / reports / bug-reports) plus an optional
// bucket-summary endpoint on user click.
//
// Per D-02 "full happy path per admin tab/section" the happy-path test asserts
// each of the 7 StatPanel section headings renders: Users & vehicles / Builds
// & logs / Parts & catalog / Crawling & listings / Media & storage / Community
// / System. We also assert specific numeric values surface from the stats API
// response (e.g. 42 users) so the StatRow pipeline end-to-end is exercised.
//
// Auth-deny coverage mirrors AdminDashboard.test.tsx — null user shows the
// "please log in" ErrorAlert; non-admin user shows the permission-denied
// ErrorAlert.
//
// Mocking strategy: setup.ts registers the global `vi.mock('../api/client')`,
// so the real `adminApi`/`usersApi`/etc. domain modules run, each calling
// `apiClient.get(...)` which lands on the shared mocked Axios instance. Our
// `mockImplementation` below routes each URL substring to the appropriate
// payload shape.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  testScenarios,
} from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import { mockUser } from '../../test/mocks/api';
import { makeSystemStats } from '../../test/mocks/admin/stats';
import SystemStatistics from './SystemStatistics';

// Non-admin authenticated scenario built from canonical typed mockUser so we
// sidestep the stale shape in testScenarios.authenticated.initialAuthState.user
// (see AdminDashboard.test.tsx for the rationale).
const nonAdminAuthenticated = {
  initialAuthState: {
    isAuthenticated: true,
    user: { ...mockUser, is_admin: false },
    isLoading: false,
  },
};

/**
 * Route every GET request SystemStatistics makes to a payload matching that
 * endpoint's response shape. Unknown URLs fall through to a generic
 * `{ count: 0 }` — the page tolerates missing values gracefully (renders '—'),
 * but explicit routes let us assert specific metric values downstream.
 */
function seedStatsApi(stats = makeSystemStats()) {
  const countByUrl: Record<string, number> = {
    '/users/count': 42,
    '/car-generations/count': 7,
    '/car-generations/makes/count': 5,
    '/car-generations/car-models/count': 6,
    '/build-lists/count': 13,
    '/parts/count': 88,
    '/categories/count': 9,
    '/part-manufacturers/count': 11,
    '/retailers/count': 4,
    '/build-logs/posts/count': 22,
    '/build-list-parts/count': 17,
    '/votes/count': 3,
    '/reports/count': 2,
    '/bug-reports/count': 1,
  };

  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/admin/stats/table-counts') {
      return Promise.resolve({ data: stats });
    }
    if (url === '/admin/stats/crawl-bucket') {
      return Promise.resolve({
        data: {
          crawl_bucket_configured: true,
          crawl_bucket_total: 0,
          crawl_bucket_by_prefix: {},
          crawl_bucket_size_gb: 0,
        },
      });
    }
    if (url === '/images/admin/count-by-entity-type') {
      return Promise.resolve({
        data: {
          total: 0,
          by_entity_type: {},
          other: 0,
        },
      });
    }
    if (url in countByUrl) {
      return Promise.resolve({ data: { count: countByUrl[url]! } });
    }
    return Promise.resolve({ data: { count: 0 } });
  });
}

describe('SystemStatistics page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders every stats panel heading for an admin user once counts resolve', async () => {
    seedStatsApi();

    render(<SystemStatistics />, testScenarios.adminAuthenticated);

    // H1 page header — renders synchronously (before any fetch resolves).
    expect(
      screen.getByRole('heading', { level: 1, name: /system statistics/i })
    ).toBeInTheDocument();

    // Wait for at least one known metric to surface, which implies the
    // Promise.all in fetchCounts has settled and setCounts has committed.
    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    // Each of the 7 StatPanels renders an <h3> with its title prop. D-02:
    // "full happy-path per admin tab/section" — assert every panel surfaces.
    const panelTitles = [
      'Users & vehicles',
      'Builds & logs',
      'Parts & catalog',
      'Crawling & listings',
      'Media & storage',
      'Community',
      'System',
    ];
    for (const title of panelTitles) {
      expect(
        screen.getByRole('heading', { level: 3, name: title })
      ).toBeInTheDocument();
    }

    // "System Statistics" SectionHeader (h2) + page-header (h1) both render.
    expect(
      screen.getByRole('heading', { level: 2, name: /system statistics/i })
    ).toBeInTheDocument();
  });

  it('renders specific metric values from the stats API response', async () => {
    // Seed a custom AdminTableCountsResponse so we can assert a non-default
    // value flows through the admin-table block (build_logs / part_cars).
    seedStatsApi(
      makeSystemStats({
        build_logs: 99,
        part_cars: 321,
        background_jobs: 456,
      })
    );

    render(<SystemStatistics />, testScenarios.adminAuthenticated);

    // All metric rows surface their number once Promise.all settles.
    await waitFor(() => {
      // Users count from the /users/count route (42).
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    // Plain-count endpoints rendered by StatRow.
    expect(screen.getByText('88')).toBeInTheDocument(); // parts
    expect(screen.getByText('13')).toBeInTheDocument(); // build lists
    expect(screen.getByText('22')).toBeInTheDocument(); // build log posts

    // admin-table supplemental counts also surface (via StatRow).
    // Values chosen to not collide with the plain-count fixture values above.
    expect(screen.getByText('99')).toBeInTheDocument(); // build_logs
    expect(screen.getByText('321')).toBeInTheDocument(); // part_cars
    expect(screen.getByText('456')).toBeInTheDocument(); // background_jobs

    // Refresh button present once loading completes.
    expect(
      screen.getByRole('button', { name: /refresh$/i })
    ).toBeInTheDocument();
  });

  it('denies access to an authenticated non-admin user', () => {
    render(<SystemStatistics />, nonAdminAuthenticated);

    expect(
      screen.getByText(
        /you do not have permission to access the admin dashboard/i
      )
    ).toBeInTheDocument();

    // None of the panel headings or refresh buttons render in this branch.
    expect(
      screen.queryByRole('heading', { level: 3, name: /users & vehicles/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /refresh$/i })
    ).not.toBeInTheDocument();
  });

  it('prompts an unauthenticated visitor to log in', () => {
    render(<SystemStatistics />, testScenarios.unauthenticated);

    expect(
      screen.getByText(/please log in to access the admin dashboard/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { level: 3, name: /users & vehicles/i })
    ).not.toBeInTheDocument();
  });
});
