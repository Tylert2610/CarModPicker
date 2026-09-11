/**
 * User bug report submission plus the admin triage list.
 */

import { apiClient } from './client';
import type {
  BugReportCreate,
  BugReportRead,
  BugReportUpdate,
  BugReportWithDetails,
  PaginatedResponse,
} from '../types/Api';

/** Bug report submission and the admin triage endpoints. */
export const bugReportsApi = {
  createBugReport: (data: BugReportCreate) =>
    apiClient.post<BugReportRead>('/bug-reports/', data),
  getBugReports: (params?: {
    status?: string;
    priority?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<BugReportRead[]>('/bug-reports/admin/list', {
      params,
    }),
  getBugReportsWithDetails: (params?: {
    status?: string;
    priority?: string;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<PaginatedResponse<BugReportWithDetails>>(
      '/bug-reports/admin/list-with-details',
      {
        params,
      }
    ),
  getBugReport: (bugReportId: string) =>
    apiClient.get<BugReportWithDetails>(`/bug-reports/${bugReportId}`),
  updateBugReport: (bugReportId: string, data: BugReportUpdate) =>
    apiClient.put<BugReportRead>(`/bug-reports/${bugReportId}`, data),
  deleteBugReport: (bugReportId: string) =>
    apiClient.delete<Record<string, string>>(`/bug-reports/${bugReportId}`),
  countBugReports: () => apiClient.get<{ count: number }>('/bug-reports/count'),
};
