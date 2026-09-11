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

const nonAdminAuthenticated = {
  initialAuthState: {
    isAuthenticated: true,
    user: { ...mockUser, is_admin: false },
    isLoading: false,
  },
};

/**
 * Route every GET the page makes to a payload of that endpoint's shape.
 * Unknown URLs fall through to `{ count: 0 }`.
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

    expect(
      screen.getByRole('heading', { level: 1, name: /system statistics/i })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
    });

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

    expect(
      screen.getByRole('heading', { level: 2, name: /system statistics/i })
    ).toBeInTheDocument();
  });

  it('renders specific metric values from the stats API response', async () => {
    seedStatsApi(
      makeSystemStats({
        build_logs: 99,
        part_cars: 321,
        background_jobs: 456,
      })
    );

    render(<SystemStatistics />, testScenarios.adminAuthenticated);

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    expect(screen.getByText('88')).toBeInTheDocument();
    expect(screen.getByText('13')).toBeInTheDocument();
    expect(screen.getByText('22')).toBeInTheDocument();

    expect(screen.getByText('99')).toBeInTheDocument();
    expect(screen.getByText('321')).toBeInTheDocument();
    expect(screen.getByText('456')).toBeInTheDocument();

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
