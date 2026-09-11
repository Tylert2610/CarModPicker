import type {
  CrawlerAdapterConfig,
  CrawlerAdapterConfigList,
  CrawlerSchedule,
  CrawlerScheduleList,
} from '../../../api/admin';

/** Shape returned by `adminApi.getCrawlers()` — adapters + adapter_info. */
export interface CrawlerAdapterCatalog {
  adapters: string[];
  adapter_info: { name: string; tier: 'http' | 'tls' | 'browser' }[];
}

export const makeCrawlerAdapter = (
  overrides: Partial<CrawlerAdapterConfig> = {}
): CrawlerAdapterConfig => ({
  id: 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa',
  adapter_name: 'test-adapter',
  delay_sec: 5,
  per_run_limit: 10,
  skip_known_urls: true,
  default_category_id: '55555555-5555-7555-8555-555555555555',
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  ...overrides,
});

export const makeAdapterList = (
  items?: CrawlerAdapterConfig[]
): CrawlerAdapterConfigList => ({
  items: items ?? [makeCrawlerAdapter()],
});

export const makeAdapterCatalog = (
  overrides: Partial<CrawlerAdapterCatalog> = {}
): CrawlerAdapterCatalog => ({
  adapters: ['test-adapter'],
  adapter_info: [{ name: 'test-adapter', tier: 'http' }],
  ...overrides,
});

export const makeSchedule = (
  overrides: Partial<CrawlerSchedule> = {}
): CrawlerSchedule => ({
  id: 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb',
  name: 'weekly-all',
  description: 'Runs every Monday 03:00 UTC',
  enabled: true,
  schedule_expression: 'cron(0 3 ? * MON *)',
  last_reconciled_at: null,
  last_reconcile_error: null,
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  adapters: [{ adapter_name: 'test-adapter' }],
  ...overrides,
});

export const makeScheduleList = (
  items?: CrawlerSchedule[]
): CrawlerScheduleList => ({
  items: items ?? [makeSchedule()],
  presets: {
    monthly: 'cron(0 3 1 * ? *)',
    weekly: 'cron(0 3 ? * MON *)',
    daily: 'cron(0 3 * * ? *)',
  },
});
