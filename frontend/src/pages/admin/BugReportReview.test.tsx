/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import { mockUser } from '../../test/mocks/api';
import { makeBugReportWithDetails } from '../../test/mocks/admin/bugs';
import {
  render,
  screen,
  testScenarios,
  waitFor,
} from '../../test/utils/test-utils';
import BugReportReview from './BugReportReview';

describe('BugReportReview page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        data: [makeBugReportWithDetails({ status: 'pending' })],
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

  it('renders open (pending) bug reports list for admin user', async () => {
    render(<BugReportReview />, testScenarios.adminAuthenticated);

    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/bug-reports/admin/list-with-details',
        expect.objectContaining({
          params: expect.objectContaining({ status: 'pending' }),
        })
      )
    );
    expect(
      await screen.findByRole('heading', { name: /Test bug report/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/testuser/)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /^Review$/i })
    ).toBeInTheDocument();
  });

  it('marks a bug report in-progress (assign) via the Mark In Progress dialog action', async () => {
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        ...makeBugReportWithDetails({ status: 'in_progress' }),
      },
    });
    const user = userEvent.setup();

    render(<BugReportReview />, testScenarios.adminAuthenticated);

    const reviewBtn = await screen.findByRole('button', { name: /^Review$/i });
    await user.click(reviewBtn);

    const inProgressBtn = await screen.findByRole('button', {
      name: /Mark In Progress/i,
    });
    await user.click(inProgressBtn);

    await waitFor(() =>
      expect(vi.mocked(apiClient.put)).toHaveBeenCalledWith(
        expect.stringMatching(/^\/bug-reports\/[^/]+$/),
        expect.objectContaining({ status: 'in_progress' })
      )
    );
  });

  it('resolves a bug report via the Resolve dialog action', async () => {
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        ...makeBugReportWithDetails({ status: 'resolved' }),
      },
    });
    const user = userEvent.setup();

    render(<BugReportReview />, testScenarios.adminAuthenticated);

    const reviewBtn = await screen.findByRole('button', { name: /^Review$/i });
    await user.click(reviewBtn);

    const resolveBtn = await screen.findByRole('button', {
      name: /^Resolve$/i,
    });
    await user.click(resolveBtn);

    await waitFor(() =>
      expect(vi.mocked(apiClient.put)).toHaveBeenCalledWith(
        expect.stringMatching(/^\/bug-reports\/[^/]+$/),
        expect.objectContaining({ status: 'resolved' })
      )
    );
  });

  it('denies access to non-admin authenticated users', () => {
    render(<BugReportReview />, {
      initialAuthState: {
        isAuthenticated: true,
        user: mockUser,
        isLoading: false,
      },
    });

    expect(
      screen.getByText(
        /You do not have permission to access bug report review\./i
      )
    ).toBeInTheDocument();
    expect(vi.mocked(apiClient.put)).not.toHaveBeenCalled();
  });
});
