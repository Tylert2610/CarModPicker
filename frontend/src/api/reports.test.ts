// Phase 8 Wave 1 API-module test pattern (PATTERNS.md §7).
// `vi.mocked(apiClient.method)` and `expect(apiClient.method).toHaveBeenCalledWith(...)`
// both reference methods as unbound values; the eslint rule `@typescript-eslint/unbound-method`
// is a false positive here because vitest's mock runtime invokes them via the same
// `mockApiClient` object identity (see frontend/src/test/setup.ts dual-mock block).
// `expect.objectContaining(...)` returns `any`, which trips no-unsafe-assignment when
// passed as a property value — also a false positive in this matcher pattern.
/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { partReportsApi, reportsApi } from './reports';
import { mockBuildList, mockPart } from '../test/mocks/api';
import type {
  PaginatedResponse,
  ReportCreate,
  ReportRead,
  ReportUpdate,
  ReportWithDetails,
} from '../types/Api';

// Reusable ReportRead fixture.
const makeReportRead = (overrides: Partial<ReportRead> = {}): ReportRead => ({
  id: '77777777-7777-7777-8777-777777777777',
  user_id: '11111111-1111-7111-8111-111111111111',
  entity_type: 'part',
  entity_id: mockPart.id,
  reason: 'spam',
  description: null,
  status: 'pending',
  admin_notes: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  ...overrides,
});

const makeReportWithDetails = (
  overrides: Partial<ReportWithDetails> = {}
): ReportWithDetails => ({
  ...makeReportRead(),
  reporter_username: 'testuser',
  entity_name: 'Test Part',
  entity_description: 'Test desc',
  reviewer_username: null,
  ...overrides,
});

const emptyPaginatedReports: PaginatedResponse<ReportWithDetails> = {
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

describe('reportsApi (polymorphic)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- reportEntity — polymorphic dispatch ---

  it('reportEntity POSTs to /reports/part/:id for entity_type=part', async () => {
    const body: ReportCreate = {
      reason: 'spam',
      description: 'Looks like spam',
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: makeReportRead() });

    await reportsApi.reportEntity('part', mockPart.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/reports/part/${mockPart.id}`,
      body
    );
  });

  it('reportEntity POSTs to /reports/build_list/:id for entity_type=build_list', async () => {
    const body: ReportCreate = {
      reason: 'inappropriate_content',
      description: null,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeReportRead({
        entity_type: 'build_list',
        entity_id: mockBuildList.id,
        reason: 'inappropriate_content',
      }),
    });

    await reportsApi.reportEntity('build_list', mockBuildList.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/reports/build_list/${mockBuildList.id}`,
      body
    );
  });

  // --- getReports / getReportsWithDetails ---

  it('getReports GETs /reports/admin/list with no params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await reportsApi.getReports();

    expect(apiClient.get).toHaveBeenCalledWith('/reports/admin/list', {
      params: undefined,
    });
  });

  it('getReports forwards entity_type=part filter in params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [makeReportRead()],
    });

    await reportsApi.getReports({
      entity_type: 'part',
      status: 'pending',
      skip: 0,
      limit: 25,
    });

    expect(apiClient.get).toHaveBeenCalledWith('/reports/admin/list', {
      params: expect.objectContaining({
        entity_type: 'part',
        status: 'pending',
        skip: 0,
        limit: 25,
      }),
    });
  });

  it('getReports forwards entity_type=build_list filter in params (polymorphic)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await reportsApi.getReports({ entity_type: 'build_list' });

    expect(apiClient.get).toHaveBeenCalledWith('/reports/admin/list', {
      params: expect.objectContaining({ entity_type: 'build_list' }),
    });
  });

  it('getReportsWithDetails GETs /reports/admin/list-with-details with PaginatedResponse shape', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: emptyPaginatedReports,
    });

    const result = await reportsApi.getReportsWithDetails({
      entity_type: 'part',
      skip: 0,
      limit: 20,
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      '/reports/admin/list-with-details',
      {
        params: expect.objectContaining({
          entity_type: 'part',
          skip: 0,
          limit: 20,
        }),
      }
    );
    expect(result.data).toEqual(emptyPaginatedReports);
  });

  it('getReportsWithDetails forwards entity_type=build_list filter (polymorphic)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: emptyPaginatedReports,
    });

    await reportsApi.getReportsWithDetails({ entity_type: 'build_list' });

    expect(apiClient.get).toHaveBeenCalledWith(
      '/reports/admin/list-with-details',
      {
        params: expect.objectContaining({ entity_type: 'build_list' }),
      }
    );
  });

  // --- getMyReports (user-facing) ---

  it('getMyReports GETs /reports/my-reports with params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await reportsApi.getMyReports({ status: 'pending', skip: 0, limit: 10 });

    expect(apiClient.get).toHaveBeenCalledWith('/reports/my-reports', {
      params: expect.objectContaining({
        status: 'pending',
        skip: 0,
        limit: 10,
      }),
    });
  });

  // --- getReport ---

  it('getReport GETs /reports/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: makeReportWithDetails(),
    });

    const report = makeReportRead();
    const result = await reportsApi.getReport(report.id);

    expect(apiClient.get).toHaveBeenCalledWith(`/reports/${report.id}`);
    expect(result.data).toMatchObject({ id: report.id });
  });

  // --- updateReport ---

  it('updateReport PUTs body to /reports/:id', async () => {
    const report = makeReportRead();
    const body: ReportUpdate = {
      status: 'resolved',
      admin_notes: 'Handled',
    };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: makeReportRead({ status: 'resolved' }),
    });

    await reportsApi.updateReport(report.id, body);

    expect(apiClient.put).toHaveBeenCalledWith(`/reports/${report.id}`, body);
  });

  // --- deleteReport ---

  it('deleteReport DELETEs /reports/:id', async () => {
    const report = makeReportRead();
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'Deleted' },
    });

    await reportsApi.deleteReport(report.id);

    expect(apiClient.delete).toHaveBeenCalledWith(`/reports/${report.id}`);
  });

  // --- countReports ---

  it('countReports GETs /reports/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 9 } });

    const result = await reportsApi.countReports();

    expect(apiClient.get).toHaveBeenCalledWith('/reports/count');
    expect(result.data).toEqual({ count: 9 });
  });
});

describe('partReportsApi (legacy entity-scoped wrapper)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reportPart delegates to reportsApi.reportEntity with entity_type=part', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeReportRead(),
    });

    await partReportsApi.reportPart(mockPart.id, {
      reason: 'spam',
      description: 'Flooding the search',
    });

    expect(apiClient.post).toHaveBeenCalledWith(
      `/reports/part/${mockPart.id}`,
      { reason: 'spam', description: 'Flooding the search' }
    );
  });

  it('reportPart normalizes null description when not provided', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeReportRead(),
    });

    await partReportsApi.reportPart(mockPart.id, { reason: 'other' });

    expect(apiClient.post).toHaveBeenCalledWith(
      `/reports/part/${mockPart.id}`,
      { reason: 'other', description: null }
    );
  });

  it('getReports delegates with entity_type=part pinned in params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await partReportsApi.getReports({ status: 'reviewed', limit: 5 });

    expect(apiClient.get).toHaveBeenCalledWith('/reports/admin/list', {
      params: expect.objectContaining({
        status: 'reviewed',
        limit: 5,
        entity_type: 'part',
      }),
    });
  });

  it('updateReport delegates and coerces status/admin_notes shape', async () => {
    const report = makeReportRead();
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: makeReportRead({ status: 'dismissed' }),
    });

    await partReportsApi.updateReport(report.id, {
      status: 'dismissed',
      admin_notes: null,
    });

    expect(apiClient.put).toHaveBeenCalledWith(`/reports/${report.id}`, {
      status: 'dismissed',
      admin_notes: null,
    });
  });
});
