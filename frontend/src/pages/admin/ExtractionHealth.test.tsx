import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiClient } from '../../api/client';
import {
  render,
  screen,
  waitFor,
  testScenarios,
} from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import type { ExtractionHealthResponse } from '../../api/admin';
import ExtractionHealth from './ExtractionHealth';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

const navigateMock = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

const nonAdminAuthenticated = {
  initialAuthState: {
    isAuthenticated: true,
    user: { ...mockUser, is_admin: false },
    isLoading: false,
  },
};

const samplePayload: ExtractionHealthResponse = {
  compliance: {
    compliant: 108,
    total: 108,
    per_tier: { http: '83/83', tls: '15/15', browser: '10/10' },
  },
  coverage: {
    per_tier: {
      http: {
        parts_with_specs: 200,
        parts_total: 250,
        per_field: { brand: 0.95, weight_g: 0.5 },
      },
      tls: {
        parts_with_specs: 30,
        parts_total: 40,
        per_field: { brand: 0.8, weight_g: 0.2 },
      },
      browser: {
        parts_with_specs: 5,
        parts_total: 10,
        per_field: { brand: 0.6, weight_g: 0.1 },
      },
    },
  },
  failure_rate_7d: [
    { adapter: 'adapter-a', failed: 2, parsed: 98, rate: 0.02, tier: 'http' },
    { adapter: 'adapter-b', failed: 9, parsed: 91, rate: 0.09, tier: 'tls' },
  ],
  window: { days: 7, since: '2026-04-18T00:00:00+00:00' },
};

describe('ExtractionHealth page', () => {
  beforeEach(() => {
    navigateMock.mockReset();
    vi.mocked(apiClient.get).mockReset();
  });

  it('renders compliance numbers and per-tier pills from a mocked getExtractionHealth response', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: samplePayload });

    render(<ExtractionHealth />, testScenarios.adminAuthenticated);

    await waitFor(() => {
      expect(screen.getByText('108 / 108')).toBeInTheDocument();
    });

    expect(screen.getByTestId('compliance-pill-http')).toHaveTextContent(
      '83/83'
    );
    expect(screen.getByTestId('compliance-pill-tls')).toHaveTextContent(
      '15/15'
    );
    expect(screen.getByTestId('compliance-pill-browser')).toHaveTextContent(
      '10/10'
    );

    expect(
      screen.getByText(/Last 7 days \(since 2026-04-18T00:00:00\+00:00\)/i)
    ).toBeInTheDocument();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/extraction-health/'
    );

    const failureTable = screen.getByTestId('failure-rate-table');
    const adapterCells = failureTable.querySelectorAll('tbody tr');
    expect(adapterCells.length).toBe(2);
    expect(adapterCells[0]?.textContent).toContain('adapter-b');
    expect(adapterCells[1]?.textContent).toContain('adapter-a');
  });

  it('shows an inline ErrorAlert when the API rejects', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce({
      response: { status: 500 },
      message: 'Internal Server Error',
    });

    render(<ExtractionHealth />, testScenarios.adminAuthenticated);

    await waitFor(() => {
      expect(
        screen.getByText(/HTTP 500.*crawled_pages\.parse_status/i)
      ).toBeInTheDocument();
    });

    expect(screen.queryByText('108 / 108')).not.toBeInTheDocument();
  });

  it('redirects an authenticated non-admin user to "/"', async () => {
    render(<ExtractionHealth />, nonAdminAuthenticated);

    expect(
      screen.getByText(
        /you do not have permission to access the admin dashboard/i
      )
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/');
    });

    expect(vi.mocked(apiClient.get)).not.toHaveBeenCalledWith(
      '/admin/extraction-health/'
    );
  });
});
