/**
 * Content report fixtures for the admin tests.
 */

import type {
  PaginatedResponse,
  ReportRead,
  ReportWithDetails,
} from '../../../types/Api';

/** Builds a content report fixture, overriding any field. */
export const makeReport = (
  overrides: Partial<ReportRead> = {}
): ReportRead => ({
  id: '66666666-6666-7666-8666-666666666666',
  user_id: '11111111-1111-7111-8111-111111111111',
  entity_type: 'part',
  entity_id: '44444444-4444-7444-8444-444444444444',
  reason: 'inappropriate_content',
  description: 'Test report description',
  status: 'pending',
  admin_notes: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  ...overrides,
});

/** Builds a content report fixture carrying reporter details. */
export const makeReportWithDetails = (
  overrides: Partial<ReportWithDetails> = {}
): ReportWithDetails => ({
  ...makeReport(),
  reporter_username: 'testuser',
  entity_name: 'Test Entity',
  entity_description: 'Test entity description',
  reviewer_username: null,
  ...overrides,
});

/** Builds a list of content report fixtures. */
export const makeReportList = (items?: ReportRead[]): ReportRead[] =>
  items ?? [makeReport()];

/** Builds a list of detailed content report fixtures. */
export const makeReportWithDetailsList = (
  items?: ReportWithDetails[]
): PaginatedResponse<ReportWithDetails> => {
  const list = items ?? [makeReportWithDetails()];
  return {
    data: list,
    pagination: {
      current_page: 1,
      total_pages: 1,
      total_items: list.length,
      items_per_page: 25,
      has_next: false,
      has_previous: false,
    },
  };
};
