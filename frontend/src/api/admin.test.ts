/**
 * Tests for adminApi.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { adminApi, type ExtractionHealthResponse } from './admin';
import {
  makeSystemStats,
  makeCrawlBucketSummary,
} from '../test/mocks/admin/stats';
import {
  makeCurationCandidate,
  makeCurationQueue,
  makeUrlLookup,
  makeRescanResponse,
} from '../test/mocks/admin/curation';
import {
  makeAdapterCatalog,
  makeCrawlerAdapter,
  makeAdapterList,
  makeSchedule,
  makeScheduleList,
} from '../test/mocks/admin/crawlers';
import { makeJob, makeJobsList } from '../test/mocks/admin/jobs';

describe('adminApi — migrations & db-ops', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runMigrations POSTs to /admin/db-ops/migrations/run', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        success: true,
        output: 'upgraded',
        error: null,
        current_revision: 'abc123',
      },
    });

    await adminApi.runMigrations();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/migrations/run'
    );
  });

  it('getCurrentRevision GETs /admin/db-ops/migrations/current', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { current_revision: 'abc123', output: 'ok' },
    });

    await adminApi.getCurrentRevision();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/db-ops/migrations/current'
    );
  });

  it('initCarGenerations POSTs to /admin/db-ops/init/car-generations', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { success: true, message: 'seeded' },
    });

    await adminApi.initCarGenerations();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/init/car-generations'
    );
  });

  it('initPartCategories POSTs to /admin/db-ops/init/part-categories', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { success: true, message: 'seeded' },
    });

    await adminApi.initPartCategories();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/init/part-categories'
    );
  });

  it('deleteAllParts POSTs to /admin/db-ops/parts/delete-all', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { deleted_count: 42 },
    });

    const result = await adminApi.deleteAllParts();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/parts/delete-all'
    );
    expect(result.data.deleted_count).toBe(42);
  });

  it('deleteAllCars POSTs to /admin/db-ops/cars/delete-all', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        deleted_count: 5,
        deleted_car_models_count: 10,
        deleted_makes_count: 3,
      },
    });

    const result = await adminApi.deleteAllCars();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/cars/delete-all'
    );
    expect(result.data.deleted_makes_count).toBe(3);
  });

  it('deleteAllPartManufacturers POSTs to /admin/db-ops/part-manufacturers/delete-all', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { deleted_count: 7 },
    });

    await adminApi.deleteAllPartManufacturers();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/db-ops/part-manufacturers/delete-all'
    );
  });
});

describe('adminApi — system stats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getTableCounts GETs /admin/stats/table-counts', async () => {
    const stats = makeSystemStats({ crawled_pages: 123, part_listings: 456 });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: stats });

    const result = await adminApi.getTableCounts();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/stats/table-counts'
    );
    expect(result.data).toEqual(stats);
    expect(result.data.crawled_pages).toBe(123);
  });

  it('getTableCounts returns vote/report polymorphic breakdown', async () => {
    const stats = makeSystemStats({
      votes_by_entity_type: { part: 10, build_list: 5 },
      reports_by_entity_type: { part: 2 },
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: stats });

    const result = await adminApi.getTableCounts();

    expect(result.data.votes_by_entity_type).toEqual({
      part: 10,
      build_list: 5,
    });
    expect(result.data.reports_by_entity_type).toEqual({ part: 2 });
  });

  it('getCrawlBucketSummary GETs /admin/stats/crawl-bucket', async () => {
    const summary = makeCrawlBucketSummary({
      crawl_bucket_total: 9999,
      crawl_bucket_by_prefix: { 'adapter-a/': 5000, 'adapter-b/': 4999 },
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: summary });

    const result = await adminApi.getCrawlBucketSummary();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/stats/crawl-bucket'
    );
    expect(result.data.crawl_bucket_total).toBe(9999);
  });
});

describe('adminApi — crawled page counts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCrawledPageCountsBySource GETs /crawled-pages/counts-by-source', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { 'adapter-a': 100, chrome_extension: 50 },
    });

    const result = await adminApi.getCrawledPageCountsBySource();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/crawled-pages/counts-by-source'
    );
    expect(result.data['adapter-a']).toBe(100);
  });

  it('getCrawledPageCountsBySourceAndStatus GETs /crawled-pages/counts-by-source-and-status', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        'adapter-a': { parsed: 80, pending: 20 },
        chrome_extension: { parsed: 50, pending: 0 },
      },
    });

    const result = await adminApi.getCrawledPageCountsBySourceAndStatus();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/crawled-pages/counts-by-source-and-status'
    );
    expect(result.data['adapter-a']?.['parsed']).toBe(80);
  });
});

describe('adminApi — crawlers base', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCrawlers GETs /admin/crawlers and returns adapter catalog', async () => {
    const catalog = makeAdapterCatalog();
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: catalog });

    const result = await adminApi.getCrawlers();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith('/admin/crawlers/');
    expect(result.data.adapters).toEqual(['test-adapter']);
    expect(result.data.adapter_info[0]?.tier).toBe('http');
  });

  it('runCrawlers POSTs body to /admin/crawlers/run', async () => {
    const body = {
      adapters: ['test-adapter'],
      crawler_default_category_id: '55555555-5555-7555-8555-555555555555',
      global_limit: 100,
      parallel: false,
      delay_sec: 5,
      skip_known_urls: true,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        status: 'started',
        job_id: '99999999-9999-7999-8999-999999999999',
        adapters: ['test-adapter'],
        triggered_by: 'manual',
        message: 'started',
      },
    });

    const result = await adminApi.runCrawlers(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawlers/run',
      body
    );
    expect(result.data.status).toBe('started');
  });
});

describe('adminApi — archive rescrape', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('rescrapeArchives POSTs body to /admin/crawlers/rescrape-archives', async () => {
    const body = {
      default_category_id: '55555555-5555-7555-8555-555555555555',
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        status: 'queued',
        job_id: '88888888-8888-7888-8888-888888888888',
        triggered_by: 'manual',
        message: 'queued',
      },
    });

    const result = await adminApi.rescrapeArchives(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawlers/rescrape-archives',
      body
    );
    expect(result.data.job_id).toBe('88888888-8888-7888-8888-888888888888');
  });

  it('rescrapeArchives forwards optional crawler_user_id override', async () => {
    const body = {
      crawler_user_id: '33333333-3333-7333-8333-333333333333',
      default_category_id: '55555555-5555-7555-8555-555555555555',
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        status: 'queued',
        job_id: 'x',
        triggered_by: 'manual',
        message: 'ok',
      },
    });

    await adminApi.rescrapeArchives(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawlers/rescrape-archives',
      expect.objectContaining({
        crawler_user_id: '33333333-3333-7333-8333-333333333333',
      })
    );
  });
});

describe('adminApi — canonical-part curation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getPartLinkGroup GETs /admin/parts/:id/link-group', async () => {
    const group = makeCurationQueue([makeCurationCandidate({ name: 'Alpha' })]);
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: group });
    const partId = 'dddddddd-dddd-7ddd-8ddd-dddddddddddd';

    const result = await adminApi.getPartLinkGroup(partId);

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/admin/parts/${partId}/link-group`
    );
    expect(result.data.members[0]?.name).toBe('Alpha');
  });

  it('lookupPartsByProductUrl GETs /admin/parts/lookup-by-url with url param', async () => {
    const lookup = makeUrlLookup({
      normalized_url: 'https://example.com/x',
      matches: [],
    });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: lookup });

    await adminApi.lookupPartsByProductUrl('https://example.com/x');

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/parts/lookup-by-url',
      { params: { url: 'https://example.com/x' } }
    );
  });

  it('promotePartToCanonical POSTs part_id body to /admin/parts/promote-canonical', async () => {
    const candidate = makeCurationCandidate();
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { canonical_id: candidate.id, members: [candidate] },
    });

    await adminApi.promotePartToCanonical(candidate.id);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/parts/promote-canonical',
      { part_id: candidate.id }
    );
  });

  it('unlinkPartFromCanonical POSTs part_id body to /admin/parts/unlink', async () => {
    const candidate = makeCurationCandidate();
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { canonical_id: candidate.id, members: [candidate] },
    });

    await adminApi.unlinkPartFromCanonical(candidate.id);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/parts/unlink',
      { part_id: candidate.id }
    );
  });

  it('manuallyLinkParts POSTs duplicate_id + canonical_id to /admin/parts/link', async () => {
    const body = {
      duplicate_id: 'eeeeeeee-eeee-7eee-8eee-eeeeeeeeeeee',
      canonical_id: 'cccccccc-cccc-7ccc-8ccc-cccccccccccc',
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { canonical_id: body.canonical_id, members: [] },
    });

    await adminApi.manuallyLinkParts(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/parts/link',
      body
    );
  });

  it('rescanPartsForCanonicalLinking POSTs dry_run + batch_size to /admin/parts/rescan', async () => {
    const body = { dry_run: true, batch_size: 100 };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeRescanResponse({ scanned: 100, changes: 3 }),
    });

    const result = await adminApi.rescanPartsForCanonicalLinking(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/parts/rescan',
      body
    );
    expect(result.data.scanned).toBe(100);
    expect(result.data.changes).toBe(3);
  });
});

describe('adminApi — background jobs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('listJobs GETs /admin/jobs/ with no params when none provided', async () => {
    const jobs = makeJobsList();
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: jobs });

    const result = await adminApi.listJobs();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith('/admin/jobs/', {
      params: undefined,
    });
    expect(result.data.items[0]?.job_type).toBe('crawler_run');
  });

  it('listJobs forwards status/job_type/limit/offset filters', async () => {
    const jobs = makeJobsList({ running: true });
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: jobs });
    const params = {
      status: 'running',
      job_type: 'crawler_run',
      limit: 10,
      offset: 20,
    };

    await adminApi.listJobs(params);

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith('/admin/jobs/', {
      params,
    });
  });

  it('getJob GETs /admin/jobs/:id', async () => {
    const job = makeJob();
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: job });

    await adminApi.getJob(job.id);

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/admin/jobs/${job.id}`
    );
  });

  it('getCrawlerJobProgress GETs /admin/jobs/:id/crawler-progress', async () => {
    const jobId = '99999999-9999-7999-8999-999999999999';
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        job_id: jobId,
        status: 'running',
        started_at: '2026-04-24T00:00:00Z',
        now: '2026-04-24T00:05:00Z',
        adapters: {
          'adapter-a': { parsed_this_run: 25, last_parsed_at: null },
        },
      },
    });

    const result = await adminApi.getCrawlerJobProgress(jobId);

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/admin/jobs/${jobId}/crawler-progress`
    );
    expect(result.data.adapters['adapter-a']?.parsed_this_run).toBe(25);
  });

  it('cancelJob POSTs to /admin/jobs/:id/cancel', async () => {
    const job = makeJob({ status: 'cancelled' });
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: job });

    const result = await adminApi.cancelJob(job.id);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      `/admin/jobs/${job.id}/cancel`
    );
    expect(result.data.status).toBe('cancelled');
  });
});

describe('adminApi — crawler schedules', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('listCrawlerSchedules GETs /admin/crawler-schedules/', async () => {
    const list = makeScheduleList();
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: list });

    const result = await adminApi.listCrawlerSchedules();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/crawler-schedules/'
    );
    expect(Object.keys(result.data.presets)).toContain('weekly');
  });

  it('createCrawlerSchedule POSTs body to /admin/crawler-schedules/', async () => {
    const body = {
      name: 'nightly-all',
      description: 'Runs every night',
      enabled: true,
      schedule_expression: 'cron(0 0 * * ? *)',
      adapters: ['test-adapter'],
    };
    const schedule = makeSchedule({ name: body.name });
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: schedule });

    await adminApi.createCrawlerSchedule(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawler-schedules/',
      body
    );
  });

  it('createCrawlerSchedule accepts preset shorthand in body', async () => {
    const body = {
      name: 'weekly-all',
      preset: 'weekly' as const,
      adapters: ['test-adapter'],
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeSchedule({ name: body.name }),
    });

    await adminApi.createCrawlerSchedule(body);

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawler-schedules/',
      expect.objectContaining({ preset: 'weekly' })
    );
  });

  it('updateCrawlerSchedule PATCHes /admin/crawler-schedules/:id', async () => {
    const scheduleId = 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb';
    const body = { enabled: false, description: 'paused' };
    vi.mocked(apiClient.patch).mockResolvedValueOnce({
      data: makeSchedule({ id: scheduleId, enabled: false }),
    });

    await adminApi.updateCrawlerSchedule(scheduleId, body);

    expect(vi.mocked(apiClient.patch)).toHaveBeenCalledWith(
      `/admin/crawler-schedules/${scheduleId}`,
      body
    );
  });

  it('deleteCrawlerSchedule DELETEs /admin/crawler-schedules/:id', async () => {
    const scheduleId = 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb';
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: undefined });

    await adminApi.deleteCrawlerSchedule(scheduleId);

    expect(vi.mocked(apiClient.delete)).toHaveBeenCalledWith(
      `/admin/crawler-schedules/${scheduleId}`
    );
  });

  it('reconcileCrawlerSchedules POSTs to /admin/crawler-schedules/reconcile', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        results: [{ schedule_name: 'weekly-all', ok: true, error: null }],
      },
    });

    const result = await adminApi.reconcileCrawlerSchedules();

    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawler-schedules/reconcile'
    );
    expect(result.data.results[0]?.ok).toBe(true);
  });
});

describe('adminApi — crawler adapter configs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('listCrawlerAdapterConfigs GETs /admin/crawler-adapter-configs/', async () => {
    const list = makeAdapterList([makeCrawlerAdapter({ delay_sec: 10 })]);
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: list });

    const result = await adminApi.listCrawlerAdapterConfigs();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/crawler-adapter-configs/'
    );
    expect(result.data.items[0]?.delay_sec).toBe(10);
  });

  it('updateCrawlerAdapterConfig PATCHes /admin/crawler-adapter-configs/:name with body', async () => {
    const adapterName = 'test-adapter';
    const body = {
      delay_sec: 15,
      per_run_limit: 50,
      skip_known_urls: false,
    };
    vi.mocked(apiClient.patch).mockResolvedValueOnce({
      data: makeCrawlerAdapter({
        adapter_name: adapterName,
        delay_sec: 15,
        per_run_limit: 50,
        skip_known_urls: false,
      }),
    });

    await adminApi.updateCrawlerAdapterConfig(adapterName, body);

    expect(vi.mocked(apiClient.patch)).toHaveBeenCalledWith(
      `/admin/crawler-adapter-configs/${adapterName}`,
      body
    );
  });

  it('updateCrawlerAdapterConfig supports clear_per_run_limit flag', async () => {
    const adapterName = 'test-adapter';
    const body = { clear_per_run_limit: true };
    vi.mocked(apiClient.patch).mockResolvedValueOnce({
      data: makeCrawlerAdapter({
        adapter_name: adapterName,
        per_run_limit: null,
      }),
    });

    await adminApi.updateCrawlerAdapterConfig(adapterName, body);

    expect(vi.mocked(apiClient.patch)).toHaveBeenCalledWith(
      `/admin/crawler-adapter-configs/${adapterName}`,
      expect.objectContaining({ clear_per_run_limit: true })
    );
  });
});

describe('adminApi — extraction health', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getExtractionHealth GETs /admin/extraction-health/ and returns the typed payload', async () => {
    const payload: ExtractionHealthResponse = {
      compliance: {
        compliant: 108,
        total: 108,
        per_tier: { http: '83/83', tls: '15/15', browser: '10/10' },
      },
      coverage: {
        per_tier: {
          http: {
            parts_with_specs: 200,
            parts_total: 250,
            per_field: { brand: 0.95, weight_g: 0.5 },
          },
          tls: {
            parts_with_specs: 30,
            parts_total: 40,
            per_field: { brand: 0.8, weight_g: 0.2 },
          },
          browser: {
            parts_with_specs: 5,
            parts_total: 10,
            per_field: { brand: 0.6, weight_g: 0.1 },
          },
        },
      },
      failure_rate_7d: [
        {
          adapter: 'test-adapter',
          failed: 2,
          parsed: 98,
          rate: 0.02,
          tier: 'http',
        },
      ],
      window: { days: 7, since: '2026-04-18T00:00:00+00:00' },
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: payload });

    const result = await adminApi.getExtractionHealth();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/extraction-health/'
    );
    expect(result.data).toEqual(payload);
    expect(result.data.compliance.compliant).toBe(108);
    expect(result.data.coverage.per_tier.http.per_field['brand']).toBe(0.95);
    expect(result.data.failure_rate_7d[0]?.rate).toBe(0.02);
    expect(result.data.window.days).toBe(7);
  });
});
