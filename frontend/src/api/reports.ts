// Reports domain API. Mirrors backend endpoints/reports.py (polymorphic).
// Polymorphic `reportsApi` is the canonical surface; `partReportsApi` is a
// thin entity-typed wrapper kept for existing callers.
import { apiClient } from './client';
import type {
  PaginatedResponse,
  ReportCreate,
  ReportRead,
  ReportUpdate,
  ReportWithDetails,
} from '../types/Api';

export const reportsApi = {
  reportEntity: (
    entityType: 'build_list' | 'part',
    entityId: string,
    data: ReportCreate
  ) => apiClient.post<ReportRead>(`/reports/${entityType}/${entityId}`, data),
  getReports: (params?: {
    entity_type?: 'build_list' | 'part';
    status?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<ReportRead[]>('/reports/admin/list', {
      params,
    }),
  getReportsWithDetails: (params?: {
    entity_type?: 'build_list' | 'part';
    status?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<PaginatedResponse<ReportWithDetails>>(
      '/reports/admin/list-with-details',
      {
        params,
      }
    ),
  getMyReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    apiClient.get<ReportRead[]>('/reports/my-reports', { params }),
  getReport: (reportId: string) =>
    apiClient.get<ReportWithDetails>(`/reports/${reportId}`),
  updateReport: (reportId: string, data: ReportUpdate) =>
    apiClient.put<ReportRead>(`/reports/${reportId}`, data),
  deleteReport: (reportId: string) =>
    apiClient.delete<Record<string, string>>(`/reports/${reportId}`),
  countReports: () => apiClient.get<{ count: number }>('/reports/count'),
};

// Legacy part-scoped wrapper (callers should migrate to reportsApi).
export const partReportsApi = {
  reportPart: (
    partId: string,
    data: { reason: string; description?: string | null }
  ) =>
    reportsApi.reportEntity('part', partId, {
      reason: data.reason as
        'inappropriate_content' | 'spam' | 'inaccurate' | 'duplicate' | 'other',
      description: data.description ?? null,
    }),
  getReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    reportsApi.getReports({ ...params, entity_type: 'part' }),
  getReport: (reportId: string) => reportsApi.getReport(reportId),
  updateReport: (
    reportId: string,
    data: { status: string; admin_notes?: string | null }
  ) =>
    reportsApi.updateReport(reportId, {
      status: data.status as 'pending' | 'reviewed' | 'resolved' | 'dismissed',
      admin_notes: data.admin_notes ?? null,
    }),
};
