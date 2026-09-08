/* eslint-disable @typescript-eslint/no-unsafe-assignment --
 * vi.mocked(apiClient.put) is the canonical Phase 8 mocking pattern.
 * `expect.objectContaining(...)` returns `any` and trips no-unsafe-assignment
 * when nested as a property value — false positive in this matcher pattern.
 */

// Phase 8 plan 08-17 (D-02) — ReportReview admin page: pending-list render +
// resolve (approve) + dismiss (reject) + auth-deny for non-admin.
//
// ReportReview imports `apiClient` from `../../api/client` and `reportsApi`
// from `../../api/reports`. setup.ts mocks the client and the domain module
// calls through it (reportsApi.getReportsWithDetails -> apiClient.get), so no
// per-file vi.mock is needed.
//
// Update path: page calls `apiClient.put('/reports/<id>', { status, admin_notes })`
// with status='resolved' (Resolve Report button) or status='dismissed' (Dismiss
// Report button). Per plan <action> note: "Adjust URL shapes per actual source."

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import { mockUser } from '../../test/mocks/api';
import { makeReportWithDetails } from '../../test/mocks/admin/reports';
import {
  render,
  screen,
  testScenarios,
  waitFor,
} from '../../test/utils/test-utils';
import ReportReview from './ReportReview';

describe('ReportReview page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Route list + count fetches through a single paginated response. Both the
    // getReportsWithDetails() list call and the `status: 'pending', limit: 1`
    // count call hit /reports/admin/list-with-details via apiClient.get.
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        data: [makeReportWithDetails({ status: 'pending' })],
        pagination: {
          current_page: 1,
          total_pages: 1,
          total_items: 1,
          items_per_page: 10,
          has_next: false,
          has_previous: false,
        },
      },
    });
  });

  it('renders pending reports list for admin user', async () => {
    render(<ReportReview />, testScenarios.adminAuthenticated);

    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/reports/admin/list-with-details',
        expect.objectContaining({
          params: expect.objectContaining({ status: 'pending' }),
        })
      )
    );
    // Report row renders title / reporter / entity name.
    expect(
      await screen.findByRole('heading', { name: /Report #/i })
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Test Entity/).length).toBeGreaterThan(0);
    // The Review action button is visible on pending rows.
    expect(
      screen.getByRole('button', { name: /^Review$/i })
    ).toBeInTheDocument();
  });

  it('resolves (approves) a report via the Resolve Report dialog action', async () => {
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        ...makeReportWithDetails({ status: 'resolved' }),
      },
    });
    const user = userEvent.setup();

    render(<ReportReview />, testScenarios.adminAuthenticated);

    // Open the review dialog
    const reviewBtn = await screen.findByRole('button', { name: /^Review$/i });
    await user.click(reviewBtn);

    // Click the green Resolve Report action inside the dialog
    const resolveBtn = await screen.findByRole('button', {
      name: /Resolve Report/i,
    });
    await user.click(resolveBtn);

    await waitFor(() =>
      expect(vi.mocked(apiClient.put)).toHaveBeenCalledWith(
        expect.stringMatching(/^\/reports\/[^/]+$/),
        expect.objectContaining({ status: 'resolved' })
      )
    );
  });

  it('dismisses (rejects) a report via the Dismiss Report dialog action', async () => {
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        ...makeReportWithDetails({ status: 'dismissed' }),
      },
    });
    const user = userEvent.setup();

    render(<ReportReview />, testScenarios.adminAuthenticated);

    const reviewBtn = await screen.findByRole('button', { name: /^Review$/i });
    await user.click(reviewBtn);

    const dismissBtn = await screen.findByRole('button', {
      name: /Dismiss Report/i,
    });
    await user.click(dismissBtn);

    await waitFor(() =>
      expect(vi.mocked(apiClient.put)).toHaveBeenCalledWith(
        expect.stringMatching(/^\/reports\/[^/]+$/),
        expect.objectContaining({ status: 'dismissed' })
      )
    );
  });

  it('denies access to non-admin authenticated users', () => {
    // Use mockUser (non-admin) inline to avoid the pre-existing typing gap in
    // testScenarios.authenticated's createMockUser helper (id: number + missing
    // subscription fields vs. UserRead).
    render(<ReportReview />, {
      initialAuthState: {
        isAuthenticated: true,
        user: mockUser,
        isLoading: false,
      },
    });

    expect(
      screen.getByText(/You do not have permission to access report review\./i)
    ).toBeInTheDocument();
    // List fetch should NOT fire for non-admin — the early return runs first,
    // and the fetch useEffect requires user.is_admin.
    expect(vi.mocked(apiClient.put)).not.toHaveBeenCalled();
  });
});
