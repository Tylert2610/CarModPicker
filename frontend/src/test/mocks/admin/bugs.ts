import type {
  BugReportRead,
  BugReportWithDetails,
  PaginatedResponse,
} from '../../../types/Api';

export const makeBugReport = (
  overrides: Partial<BugReportRead> = {}
): BugReportRead => ({
  id: '77777777-7777-7777-8777-777777777777',
  user_id: '11111111-1111-7111-8111-111111111111',
  title: 'Test bug report',
  description: 'Something is broken',
  steps_to_reproduce: '1. Click foo\n2. Observe bar',
  expected_behavior: 'Should work',
  actual_behavior: 'Does not work',
  browser_info: 'test-browser',
  device_info: 'test-device',
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

export const makeBugReportWithDetails = (
  overrides: Partial<BugReportWithDetails> = {}
): BugReportWithDetails => ({
  ...makeBugReport(),
  reporter_username: 'testuser',
  assignee_username: null,
  ...overrides,
});

export const makeBugReportList = (items?: BugReportRead[]): BugReportRead[] =>
  items ?? [makeBugReport()];

export const makeBugReportWithDetailsList = (
  items?: BugReportWithDetails[]
): PaginatedResponse<BugReportWithDetails> => {
  const list = items ?? [makeBugReportWithDetails()];
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
