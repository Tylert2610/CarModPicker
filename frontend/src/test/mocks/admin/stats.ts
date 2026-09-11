/**
 * Admin dashboard statistics fixtures.
 */

import type {
  AdminTableCountsResponse,
  CrawlBucketSummaryResponse,
} from '../../../api/admin';

/** Builds an admin table counts fixture. */
export const makeSystemStats = (
  overrides: Partial<AdminTableCountsResponse> = {}
): AdminTableCountsResponse => ({
  build_list_phases: 0,
  crawled_pages: 0,
  part_listings: 0,
  part_price_histories: 0,
  image_source_mappings: 0,
  build_logs: 0,
  part_cars: 0,
  background_jobs: 0,
  oauth_accounts: 0,
  webauthn_credentials: 0,
  crawler_adapter_configs: 0,
  crawler_schedules: 0,
  crawler_schedule_adapters: 0,
  votes_by_entity_type: {},
  reports_by_entity_type: {},
  ...overrides,
});

/** Builds a crawl bucket summary fixture. */
export const makeCrawlBucketSummary = (
  overrides: Partial<CrawlBucketSummaryResponse> = {}
): CrawlBucketSummaryResponse => ({
  crawl_bucket_configured: true,
  crawl_bucket_total: 0,
  crawl_bucket_by_prefix: {},
  crawl_bucket_size_gb: 0,
  ...overrides,
});
