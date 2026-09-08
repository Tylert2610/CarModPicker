// M002/S11/T03 — ExtractionHealth page coverage.
//
// Mirrors AdminDashboard.test.tsx (Wave 4) for the auth branches and follows
// the MEM094 pattern for the per-file useAuth + useNavigate mocks. The shared
// test-utils renders inside TestProviders, which seeds mockUseAuth from the
// `initialAuthState` we pass in `customRender`'s options object. The
// global vi.mock('../api/client') from setup.ts (D-18) is the same mock the
// real adminApi.getExtractionHealth() resolves through, so seeding
// vi.mocked(apiClient.get) here drives the page's data-fetch effect.

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

// MEM094: vi.mock is hoisted per-file, so the mirror declaration in
// test-utils.tsx does NOT auto-apply here. Declare the useAuth mock
// explicitly so the page's hook resolves to the test-controlled
// mockUseAuth fn that TestProviders configures via initialAuthState.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Spy on useNavigate so test (c) can assert the non-admin redirect to '/'
// without actually mutating browser history.
const navigateMock = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

// Non-admin authenticated scenario built from canonical typed mockUser
// (per MEM093 — testScenarios.authenticated.user is shape-stale under
// exactOptionalPropertyTypes: true).
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

    // Compliance hero figure surfaces after the effect resolves.
    await waitFor(() => {
      expect(screen.getByText('108 / 108')).toBeInTheDocument();
    });

    // Per-tier compliance pills render with the backend-formatted strings.
    expect(screen.getByTestId('compliance-pill-http')).toHaveTextContent(
      '83/83'
    );
    expect(screen.getByTestId('compliance-pill-tls')).toHaveTextContent(
      '15/15'
    );
    expect(screen.getByTestId('compliance-pill-browser')).toHaveTextContent(
      '10/10'
    );

    // Window subtitle renders the days + since metadata.
    expect(
      screen.getByText(/Last 7 days \(since 2026-04-18T00:00:00\+00:00\)/i)
    ).toBeInTheDocument();

    // The api client was called against the documented endpoint.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/extraction-health/'
    );

    // Failure-rate table renders both rows; sorted by rate desc — adapter-b
    // (0.09) should appear before adapter-a (0.02) in document order.
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

    // The compliance hero must NOT render when the fetch failed.
    expect(screen.queryByText('108 / 108')).not.toBeInTheDocument();
  });

  it('redirects an authenticated non-admin user to "/"', async () => {
    render(<ExtractionHealth />, nonAdminAuthenticated);

    // The non-admin branch renders the permission-denied alert AND the
    // useEffect issues navigate('/'); both must be observable.
    expect(
      screen.getByText(
        /you do not have permission to access the admin dashboard/i
      )
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/');
    });

    // No data fetch should fire for a non-admin caller.
    expect(vi.mocked(apiClient.get)).not.toHaveBeenCalledWith(
      '/admin/extraction-health/'
    );
  });
});
