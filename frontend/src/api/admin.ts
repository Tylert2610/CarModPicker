// Admin domain API. Mirrors backend endpoints/admin/*.
//
// All admin-specific response types are co-located here per D-04. Re-imports
// `BucketEntityTypeCountResponse` from `./images` to avoid duplicating the
// images-bucket type that's already authoritative there.
import { apiClient } from './client';
import type { BucketEntityTypeCountResponse } from './images';

// Re-export the cross-domain images bucket type so admin call sites can pull
// it from this module alongside the admin-specific types.
export type { BucketEntityTypeCountResponse };

export interface MigrationResult {
  success: boolean;
  output: string;
  error: string | null;
  current_revision: string | null;
}

export interface CurrentRevisionResult {
  current_revision: string;
  output: string;
}

export interface InitDataResult {
  success: boolean;
  message: string;
}

export interface DeleteCrawlerPartsResult {
  deleted_count: number;
  service_account_count: number;
}

/** A persisted background job record. */
export interface BackgroundJob {
  id: string;
  job_type: 'crawler_run' | 'archive_rescrape';
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  triggered_by: 'manual' | 'scheduled';
  params: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  last_heartbeat_at: string | null;
  worker_instance_id: string | null;
  created_by_user_id: string | null;
}

export interface BackgroundJobList {
  items: BackgroundJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface CrawlerAdapterProgress {
  parsed_this_run: number;
  last_parsed_at: string | null;
}

export interface CrawlerJobProgress {
  job_id: string;
  status: string;
  started_at: string | null;
  now: string;
  adapters: Record<string, CrawlerAdapterProgress>;
}

/** Response when starting a crawler job (returns immediately; job runs in background). */
export interface CrawlerRunResponse {
  status: 'started';
  job_id: string;
  adapters: string[];
  triggered_by: 'manual' | 'scheduled';
  message: string;
}

export interface CrawlerRunRequest {
  adapters: string[];
  crawler_user_id?: string;
  crawler_default_category_id: string;
  limits?: Record<string, number>;
  global_limit?: number | null;
  parallel?: boolean;
  /** Seconds between requests per crawler (0.5–60). Default 5 for polite/heavy runs. */
  delay_sec?: number | null;
  crawl_html_save_dir?: string | null;
  /** Skip URLs already in crawled_pages with parse_status='parsed'. Useful for successive test runs. */
  skip_known_urls?: boolean;
}

/** Admin: re-parse every archived crawled page (full ingest + inference + price history when price is present). */
export interface RescrapeArchivesRequest {
  crawler_user_id?: string;
  default_category_id: string;
}

export interface RescrapeArchivesQueuedResponse {
  status: string;
  job_id: string;
  triggered_by: 'manual' | 'scheduled';
  message: string;
}

/** Admin-only: supplemental DB table row counts plus votes/reports by entity_type. */
export interface AdminTableCountsResponse {
  build_list_phases: number;
  crawled_pages: number;
  part_listings: number;
  part_price_histories: number;
  image_source_mappings: number;
  build_logs: number;
  part_cars: number;
  background_jobs: number;
  oauth_accounts: number;
  webauthn_credentials: number;
  crawler_adapter_configs: number;
  crawler_schedules: number;
  crawler_schedule_adapters: number;
  votes_by_entity_type: Record<string, number>;
  reports_by_entity_type: Record<string, number>;
}

/** Admin-only: full S3 listing of the crawl HTML bucket. On-demand; scans every key. */
export interface CrawlBucketSummaryResponse {
  /** True when CRAWL_BUCKET is set and the S3 client initialized (scraped HTML may live here). */
  crawl_bucket_configured: boolean;
  crawl_bucket_total: number;
  crawl_bucket_by_prefix: Record<string, number>;
  /** Total data stored in the crawl bucket in GB (sum of all object sizes). */
  crawl_bucket_size_gb?: number;
  /** Present when listing the crawl bucket failed after configuration. */
  crawl_bucket_error?: string;
}

/** One member of a canonical-part link group. */
export interface CanonicalLinkGroupMember {
  id: string;
  name: string;
  source: string;
  is_canonical: boolean;
  /** Linker election score; higher wins when picking a canonical. */
  richness_score: number;
  /** First image file key / URL for thumbnailing, if any. */
  image_url: string | null;
  /** Product URL at the member's retailer (from the first PartListing). */
  product_url: string | null;
  /** Retailer of the member's first PartListing. */
  retailer_id: string | null;
  created_at: string;
}

export interface CanonicalLinkGroupResponse {
  canonical_id: string;
  members: CanonicalLinkGroupMember[];
}

/** One Part whose first PartListing has a product_url matching a lookup query. */
export interface UrlLookupMatch {
  part_id: string;
  name: string;
  source: string;
  is_canonical: boolean;
  /** Canonical of this part's link group (self when canonical). */
  canonical_id: string;
  retailer_id: string | null;
}

export interface UrlLookupResponse {
  normalized_url: string;
  /**
   * All parts matching this URL. Non-UGC parts are unique on URL; UGC rows may
   * share a URL by design, so multiple matches are possible.
   */
  matches: UrlLookupMatch[];
}

/** One entry in the rescan diff: before/after canonical and the action that would be taken. */
export interface RescanDiffEntry {
  part_id: string;
  before_canonical_id: string | null;
  after_canonical_id: string | null;
  /** "link" | "reelect" | "unchanged". Only non-unchanged entries appear in the sample. */
  action: string;
}

/** Full-catalog rescan summary. */
export interface RescanResponse {
  dry_run: boolean;
  scanned: number;
  changes: number;
  diff_sample: RescanDiffEntry[];
  diff_truncated: boolean;
}

/** Per-adapter retailer tuning (delay, limit, skip flag, default category). */
export interface CrawlerAdapterConfig {
  id: string;
  adapter_name: string;
  delay_sec: number;
  per_run_limit: number | null;
  skip_known_urls: boolean;
  default_category_id: string;
  created_at: string;
  updated_at: string;
}

export interface CrawlerAdapterConfigList {
  items: CrawlerAdapterConfig[];
}

export interface CrawlerAdapterConfigUpdate {
  delay_sec?: number;
  per_run_limit?: number | null;
  /** Set true to clear per_run_limit (unlimited). Takes precedence over per_run_limit. */
  clear_per_run_limit?: boolean;
  skip_known_urls?: boolean;
  default_category_id?: string;
}

/** A user-defined crawler schedule with its adapter membership. */
export interface CrawlerSchedule {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  schedule_expression: string;
  last_reconciled_at: string | null;
  last_reconcile_error: string | null;
  created_at: string;
  updated_at: string;
  adapters: { adapter_name: string }[];
}

export interface CrawlerScheduleList {
  items: CrawlerSchedule[];
  presets: Record<string, string>;
}

export interface CrawlerScheduleCreate {
  name: string;
  description?: string | null;
  enabled?: boolean;
  schedule_expression?: string;
  preset?: 'monthly' | 'weekly' | 'daily';
  adapters: string[];
}

export interface CrawlerScheduleUpdate {
  description?: string | null;
  enabled?: boolean;
  schedule_expression?: string;
  preset?: 'monthly' | 'weekly' | 'daily';
  adapters?: string[];
}

export interface CrawlerReconcileResult {
  schedule_name: string;
  ok: boolean;
  error: string | null;
}

export interface CrawlerReconcileAllResponse {
  results: CrawlerReconcileResult[];
}

// Extraction-health (admin only) — mirrors backend Pydantic models in
// `backend/app/api/endpoints/admin/extraction_health.py`. Per MEM046/D009 the
// failure-rate signal is sourced from `crawled_pages.parse_status` over a
// 7-day rolling window (NOT CloudWatch EMF). Per MEM037 the canonical adapter
// count is 108 (T0:83 / T1:15 / T2:10).

/** Per-tier coverage block: parts with any specs + per-field presence ratios. */
export interface CoverageTierBlock {
  parts_with_specs: number;
  parts_total: number;
  /** UNIVERSAL_FIELD_NAMES → presence ratio in [0, 1]. */
  per_field: Record<string, number>;
}

/** Coverage gradient keyed by fetcher tier. */
export interface CoverageBlock {
  per_tier: Record<'http' | 'tls' | 'browser', CoverageTierBlock>;
}

/** Compliance counts; per_tier values are pre-rendered "<n>/<n>" strings. */
export interface ComplianceBlock {
  compliant: number;
  total: number;
  per_tier: Record<'http' | 'tls' | 'browser', string>;
}

/** One row of the 7-day per-adapter failure-rate table. */
export interface FailureRateRow {
  adapter: string;
  failed: number;
  parsed: number;
  /** Failure ratio in [0, 1]; 0.0 when failed+parsed == 0. */
  rate: number;
  tier: string;
}

/** Window metadata describing the failure-rate aggregation period. */
export interface WindowMeta {
  days: number;
  /** ISO-8601 start of the window (UTC). */
  since: string;
}

/** Full payload from `GET /admin/extraction-health` (admin only). */
export interface ExtractionHealthResponse {
  compliance: ComplianceBlock;
  coverage: CoverageBlock;
  failure_rate_7d: FailureRateRow[];
  window: WindowMeta;
}

export const adminApi = {
  runMigrations: () =>
    apiClient.post<MigrationResult>('/admin/db-ops/migrations/run'),
  getCurrentRevision: () =>
    apiClient.get<CurrentRevisionResult>('/admin/db-ops/migrations/current'),
  initCarGenerations: () =>
    apiClient.post<InitDataResult>('/admin/db-ops/init/car-generations'),
  initPartCategories: () =>
    apiClient.post<InitDataResult>('/admin/db-ops/init/part-categories'),

  // Crawlers
  getCrawlers: () =>
    apiClient.get<{
      adapters: string[];
      adapter_info: { name: string; tier: 'http' | 'tls' | 'browser' }[];
    }>('/admin/crawlers/'),
  runCrawlers: (body: CrawlerRunRequest) =>
    apiClient.post<CrawlerRunResponse>('/admin/crawlers/run', body),

  /** Re-parse all archived HTML into parts (background job; admin only). */
  rescrapeArchives: (body: RescrapeArchivesRequest) =>
    apiClient.post<RescrapeArchivesQueuedResponse>(
      '/admin/crawlers/rescrape-archives',
      body
    ),

  /**
   * Admin: archived page count per source (adapter name or chrome_extension).
   *
   * NOTE: URL is under `/crawled-pages/...` rather than `/admin/crawled-pages/...`
   * because the backend crawled_pages router is mounted at `/crawled-pages`
   * (see backend/app/main.py EndpointRegistry). Admin-only access is enforced
   * at the handler level via `Depends(get_current_admin_user)` on
   * `count_crawled_pages_by_source` in
   * backend/app/api/endpoints/crawled_pages.py — verified in Phase 6 WR-05.
   * A non-admin token will receive 403 Forbidden from the backend.
   */
  getCrawledPageCountsBySource: () =>
    apiClient.get<Record<string, number>>('/crawled-pages/counts-by-source'),

  /**
   * Admin: per-source, per-parse_status counts — drives the parsed/total progress pill.
   *
   * Admin access is enforced by the backend handler
   * (`count_crawled_pages_by_source_and_status` uses
   * `Depends(get_current_admin_user)`); see note on
   * `getCrawledPageCountsBySource` above for the URL-prefix rationale.
   */
  getCrawledPageCountsBySourceAndStatus: () =>
    apiClient.get<Record<string, Record<string, number>>>(
      '/crawled-pages/counts-by-source-and-status'
    ),

  /** Delete all global parts (admin only). Cascades to listings, votes, reports, build list parts. */
  deleteAllParts: () =>
    apiClient.post<{ deleted_count: number }>('/admin/db-ops/parts/delete-all'),

  /** Delete only parts created by the legacy crawler service account (admin only). User and extension parts are unaffected. */
  deleteCrawlerCreatedParts: () =>
    apiClient.post<DeleteCrawlerPartsResult>(
      '/admin/db-ops/parts/delete-crawler-created'
    ),

  /** Delete all cars / car generations (admin only). Also deletes car models and makes for a clean init. */
  deleteAllCars: () =>
    apiClient.post<{
      deleted_count: number;
      deleted_car_models_count: number;
      deleted_makes_count: number;
    }>('/admin/db-ops/cars/delete-all'),

  /** Delete all part_manufacturers (admin only). Nullifies part_manufacturer on parts first, then deletes all part_manufacturers. */
  deleteAllPartManufacturers: () =>
    apiClient.post<{ deleted_count: number }>(
      '/admin/db-ops/part-manufacturers/delete-all'
    ),

  /** Supplemental table counts and polymorphic vote/report breakdown (admin only). */
  getTableCounts: () =>
    apiClient.get<AdminTableCountsResponse>('/admin/stats/table-counts'),

  /** On-demand S3 list of the crawl HTML bucket (admin only). Scans every key — slow on large buckets. */
  getCrawlBucketSummary: () =>
    apiClient.get<CrawlBucketSummaryResponse>('/admin/stats/crawl-bucket'),

  // Background jobs
  listJobs: (params?: {
    status?: string;
    job_type?: string;
    limit?: number;
    offset?: number;
  }) => apiClient.get<BackgroundJobList>('/admin/jobs/', { params }),
  getJob: (jobId: string) =>
    apiClient.get<BackgroundJob>(`/admin/jobs/${jobId}`),
  getCrawlerJobProgress: (jobId: string) =>
    apiClient.get<CrawlerJobProgress>(`/admin/jobs/${jobId}/crawler-progress`),
  cancelJob: (jobId: string) =>
    apiClient.post<BackgroundJob>(`/admin/jobs/${jobId}/cancel`),

  // Crawler schedules (user-defined, N-to-N with adapters, reconciled to EventBridge)
  listCrawlerSchedules: () =>
    apiClient.get<CrawlerScheduleList>('/admin/crawler-schedules/'),
  createCrawlerSchedule: (body: CrawlerScheduleCreate) =>
    apiClient.post<CrawlerSchedule>('/admin/crawler-schedules/', body),
  updateCrawlerSchedule: (scheduleId: string, body: CrawlerScheduleUpdate) =>
    apiClient.patch<CrawlerSchedule>(
      `/admin/crawler-schedules/${scheduleId}`,
      body
    ),
  deleteCrawlerSchedule: (scheduleId: string) =>
    apiClient.delete<void>(`/admin/crawler-schedules/${scheduleId}`),
  reconcileCrawlerSchedules: () =>
    apiClient.post<CrawlerReconcileAllResponse>(
      '/admin/crawler-schedules/reconcile'
    ),

  // Per-adapter retailer tuning (used by every schedule the adapter is in)
  listCrawlerAdapterConfigs: () =>
    apiClient.get<CrawlerAdapterConfigList>('/admin/crawler-adapter-configs/'),
  updateCrawlerAdapterConfig: (
    adapterName: string,
    body: CrawlerAdapterConfigUpdate
  ) =>
    apiClient.patch<CrawlerAdapterConfig>(
      `/admin/crawler-adapter-configs/${adapterName}`,
      body
    ),

  // Canonical-part curation (admin-only)
  getPartLinkGroup: (partId: string) =>
    apiClient.get<CanonicalLinkGroupResponse>(
      `/admin/parts/${partId}/link-group`
    ),
  lookupPartsByProductUrl: (url: string) =>
    apiClient.get<UrlLookupResponse>('/admin/parts/lookup-by-url', {
      params: { url },
    }),
  promotePartToCanonical: (partId: string) =>
    apiClient.post<CanonicalLinkGroupResponse>(
      '/admin/parts/promote-canonical',
      { part_id: partId }
    ),
  unlinkPartFromCanonical: (partId: string) =>
    apiClient.post<CanonicalLinkGroupResponse>('/admin/parts/unlink', {
      part_id: partId,
    }),
  manuallyLinkParts: (body: { duplicate_id: string; canonical_id: string }) =>
    apiClient.post<CanonicalLinkGroupResponse>('/admin/parts/link', body),
  rescanPartsForCanonicalLinking: (body: {
    dry_run: boolean;
    batch_size?: number;
  }) => apiClient.post<RescanResponse>('/admin/parts/rescan', body),

  /**
   * Admin extraction-health snapshot — compliance counts, per-tier coverage
   * gradient, and 7-day per-adapter failure rates. Backend handler is mounted
   * at `/admin/extraction-health/` (router prefix + `@router.get("/")`). Call
   * with the trailing slash: FastAPI's no-slash 307 redirect points at the
   * upstream (localhost:8000), which is cross-origin from the Vite dev server
   * (localhost:4000), and browsers drop the Authorization header on cross-origin
   * redirects → 401. Sources failure-rate from `crawled_pages.parse_status`
   * (D009) — works in dev/test without IAM.
   */
  getExtractionHealth: () =>
    apiClient.get<ExtractionHealthResponse>('/admin/extraction-health/'),
};
