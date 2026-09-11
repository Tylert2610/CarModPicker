/* eslint-disable @typescript-eslint/no-unsafe-assignment */

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
    expect(
      await screen.findByRole('heading', { name: /Report #/i })
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Test Entity/).length).toBeGreaterThan(0);
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

    const reviewBtn = await screen.findByRole('button', { name: /^Review$/i });
    await user.click(reviewBtn);

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
    expect(vi.mocked(apiClient.put)).not.toHaveBeenCalled();
  });
});
