/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { bugReportsApi } from './bug_reports';
import type {
  BugReportCreate,
  BugReportRead,
  BugReportUpdate,
  BugReportWithDetails,
  PaginatedResponse,
} from '../types/Api';

const makeBugReport = (
  overrides: Partial<BugReportRead> = {}
): BugReportRead => ({
  id: '88888888-8888-7888-8888-888888888888',
  user_id: '11111111-1111-7111-8111-111111111111',
  title: 'Crash on login',
  description: 'Login button explodes',
  steps_to_reproduce: null,
  expected_behavior: null,
  actual_behavior: null,
  browser_info: null,
  device_info: null,
  screenshot_url: null,
  status: 'pending',
  priority: 'medium',
  admin_notes: null,
  assigned_to: null,
  resolved_at: null,
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  ...overrides,
});

const makeBugReportWithDetails = (
  overrides: Partial<BugReportWithDetails> = {}
): BugReportWithDetails => ({
  ...makeBugReport(),
  reporter_username: 'testuser',
  assignee_username: null,
  ...overrides,
});

const emptyPaginatedBugs: PaginatedResponse<BugReportWithDetails> = {
  data: [],
  pagination: {
    current_page: 1,
    total_pages: 0,
    total_items: 0,
    items_per_page: 20,
    has_next: false,
    has_previous: false,
  },
};

describe('bugReportsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('createBugReport POSTs JSON body to /bug-reports/', async () => {
    const body: BugReportCreate = {
      title: 'Crash',
      description: 'desc',
      steps_to_reproduce: '1. click',
      expected_behavior: 'works',
      actual_behavior: 'fails',
      browser_info: 'Chrome 120',
      device_info: 'Linux x86_64',
      screenshot_url: null,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: makeBugReport() });

    await bugReportsApi.createBugReport(body);

    expect(apiClient.post).toHaveBeenCalledWith('/bug-reports/', body);
    const postCalls = vi.mocked(apiClient.post).mock.calls;
    expect(postCalls.length).toBeGreaterThan(0);
    const firstCall = postCalls[0];
    expect(firstCall?.[1]).not.toBeInstanceOf(FormData);
  });

  it('getBugReports GETs /bug-reports/admin/list with status + priority params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [makeBugReport()],
    });

    await bugReportsApi.getBugReports({
      status: 'pending',
      priority: 'high',
      skip: 0,
      limit: 25,
    });

    expect(apiClient.get).toHaveBeenCalledWith('/bug-reports/admin/list', {
      params: expect.objectContaining({
        status: 'pending',
        priority: 'high',
        skip: 0,
        limit: 25,
      }),
    });
  });

  it('getBugReports GETs /bug-reports/admin/list with no params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await bugReportsApi.getBugReports();

    expect(apiClient.get).toHaveBeenCalledWith('/bug-reports/admin/list', {
      params: undefined,
    });
  });

  it('getBugReportsWithDetails GETs /bug-reports/admin/list-with-details with PaginatedResponse shape', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: emptyPaginatedBugs,
    });

    const result = await bugReportsApi.getBugReportsWithDetails({
      status: 'resolved',
      skip: 0,
      limit: 20,
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      '/bug-reports/admin/list-with-details',
      {
        params: expect.objectContaining({
          status: 'resolved',
          skip: 0,
          limit: 20,
        }),
      }
    );
    expect(result.data).toEqual(emptyPaginatedBugs);
  });

  it('getBugReport GETs /bug-reports/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: makeBugReportWithDetails(),
    });

    const bug = makeBugReport();
    const result = await bugReportsApi.getBugReport(bug.id);

    expect(apiClient.get).toHaveBeenCalledWith(`/bug-reports/${bug.id}`);
    expect(result.data.id).toBe(bug.id);
  });

  it('updateBugReport PUTs body to /bug-reports/:id', async () => {
    const bug = makeBugReport();
    const body: BugReportUpdate = {
      status: 'resolved',
      priority: 'low',
      admin_notes: 'Fixed in PR #123',
      assigned_to: '11111111-1111-7111-8111-111111111111',
    };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: makeBugReport({ status: 'resolved' }),
    });

    await bugReportsApi.updateBugReport(bug.id, body);

    expect(apiClient.put).toHaveBeenCalledWith(`/bug-reports/${bug.id}`, body);
  });

  it('deleteBugReport DELETEs /bug-reports/:id', async () => {
    const bug = makeBugReport();
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'Deleted' },
    });

    await bugReportsApi.deleteBugReport(bug.id);

    expect(apiClient.delete).toHaveBeenCalledWith(`/bug-reports/${bug.id}`);
  });

  it('countBugReports GETs /bug-reports/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 3 } });

    const result = await bugReportsApi.countBugReports();

    expect(apiClient.get).toHaveBeenCalledWith('/bug-reports/count');
    expect(result.data).toEqual({ count: 3 });
  });
});
