/**
 * Background job fixtures for the admin tests.
 */

import type { BackgroundJob, BackgroundJobList } from '../../../api/admin';

/** Builds a background job fixture, overriding any field. */
export const makeJob = (
  overrides: Partial<BackgroundJob> = {}
): BackgroundJob => ({
  id: '99999999-9999-7999-8999-999999999999',
  job_type: 'crawler_run',
  status: 'completed',
  triggered_by: 'manual',
  params: null,
  result_summary: null,
  error_message: null,
  started_at: '2026-04-24T00:00:00Z',
  completed_at: '2026-04-24T00:05:00Z',
  last_heartbeat_at: null,
  worker_instance_id: null,
  created_by_user_id: null,
  ...overrides,
});

/** Builds a paged background job list response. */
export const makeJobsList = (
  opts: { running?: boolean; items?: BackgroundJob[] } = {}
): BackgroundJobList => {
  const items =
    opts.items ??
    (opts.running
      ? [makeJob({ status: 'running', completed_at: null })]
      : [makeJob()]);
  return {
    items,
    total: items.length,
    limit: 25,
    offset: 0,
  };
};
