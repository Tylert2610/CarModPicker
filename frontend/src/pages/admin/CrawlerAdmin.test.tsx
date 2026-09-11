import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

import {
  render,
  screen,
  waitFor,
  testScenarios,
} from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import {
  makeAdapterCatalog,
  makeAdapterList,
  makeCrawlerAdapter,
  makeSchedule,
  makeScheduleList,
} from '../../test/mocks/admin/crawlers';
import { makeJobsList } from '../../test/mocks/admin/jobs';
import { mockCategory, mockUser } from '../../test/mocks/api';
import {
  startFakeTimers,
  stopFakeTimers,
  advanceTimersAndFlush,
} from '../../test/utils/async';
import CrawlerAdmin from './CrawlerAdmin';

const defaultGetImpl = (url: string) => {
  if (url.startsWith('/admin/crawler-schedules'))
    return Promise.resolve({ data: makeScheduleList() });
  if (url.startsWith('/admin/crawler-adapter-configs'))
    return Promise.resolve({ data: makeAdapterList() });
  if (url.startsWith('/admin/crawlers'))
    return Promise.resolve({ data: makeAdapterCatalog() });
  if (url.startsWith('/admin/jobs'))
    return Promise.resolve({ data: makeJobsList() });
  if (url.startsWith('/crawled-pages/counts-by-source-and-status'))
    return Promise.resolve({ data: {} });
  if (url.startsWith('/categories'))
    return Promise.resolve({
      data: [
        mockCategory,
        {
          ...mockCategory,
          id: '66666666-6666-7666-8666-666666666666',
          name: 'other',
          display_name: 'Other',
          sort_order: 99,
        },
      ],
    });
  return Promise.resolve({ data: null });
};

const nonAdminAuthenticated = {
  initialAuthState: {
    isAuthenticated: true,
    user: { ...mockUser, is_admin: false },
    isLoading: false,
  },
};

describe('CrawlerAdmin — auth gating', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockImplementation(defaultGetImpl);
  });

  it('renders a "please log in" error for unauthenticated users', () => {
    render(<CrawlerAdmin />, testScenarios.unauthenticated);
    expect(
      screen.getByText(/please log in to access the admin dashboard/i)
    ).toBeInTheDocument();
  });

  it('renders a "no permission" error for authenticated non-admin users', () => {
    render(<CrawlerAdmin />, nonAdminAuthenticated);
    expect(
      screen.getByText(/do not have permission to access the admin dashboard/i)
    ).toBeInTheDocument();
  });
});

describe('CrawlerAdmin — Crawler Schedules section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockImplementation(defaultGetImpl);
  });

  it('renders the Crawler Schedules heading after mount', async () => {
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /crawler schedules/i })
      ).toBeInTheDocument()
    );
    expect(
      screen.getByRole('heading', { name: /crawler & jobs/i })
    ).toBeInTheDocument();
  });

  it('lists schedules fetched from the API', async () => {
    const seededSchedule = makeSchedule({ name: 'weekly-retailers' });
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/admin/crawler-schedules'))
        return Promise.resolve({
          data: makeScheduleList([seededSchedule]),
        });
      return defaultGetImpl(url);
    });

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    await waitFor(() =>
      expect(screen.getByText('weekly-retailers')).toBeInTheDocument()
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/crawler-schedules/'
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/crawler-adapter-configs/'
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/jobs/',
      expect.objectContaining({ params: { limit: 20 } })
    );
  });

  it('triggers a reconcile-all POST when the "Force sync with AWS" button is clicked', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { results: [] },
    });
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    const syncButton = await screen.findByRole('button', {
      name: /force sync with aws/i,
    });
    syncButton.click();

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/admin/crawler-schedules/reconcile'
      )
    );
  });
});

describe('CrawlerAdmin — Adapter Tuning section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockImplementation(defaultGetImpl);
  });

  it('renders the Adapter Tuning heading and per-retailer settings block', async () => {
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /adapter tuning/i })
      ).toBeInTheDocument()
    );
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /per-retailer settings/i })
      ).toBeInTheDocument()
    );
  });

  it('issues a PATCH when an adapter delay select is changed', async () => {
    const adapter = makeCrawlerAdapter({
      adapter_name: 'test-adapter',
      delay_sec: 5,
    });
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/admin/crawler-adapter-configs'))
        return Promise.resolve({ data: makeAdapterList([adapter]) });
      return defaultGetImpl(url);
    });
    vi.mocked(apiClient.patch).mockResolvedValue({
      data: { ...adapter, delay_sec: 10 },
    });

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    const delayEl = await screen.findByTitle('Delay');
    const delaySelect = delayEl as HTMLSelectElement;
    expect(delaySelect.value).toBe('5');
    delaySelect.value = '10';
    delaySelect.dispatchEvent(new Event('change', { bubbles: true }));

    await waitFor(() =>
      expect(vi.mocked(apiClient.patch)).toHaveBeenCalledWith(
        '/admin/crawler-adapter-configs/test-adapter',
        expect.objectContaining({ delay_sec: 10 })
      )
    );
    expect(vi.mocked(apiClient.patch)).toHaveBeenCalledTimes(1);
  });
});

describe('CrawlerAdmin — Background Jobs section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    stopFakeTimers();
  });

  it('renders the Background Jobs heading', async () => {
    vi.mocked(apiClient.get).mockImplementation(defaultGetImpl);
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /background jobs/i })
      ).toBeInTheDocument()
    );
  });

  it('polls /admin/jobs every 5 s while a job is running', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/admin/jobs'))
        return Promise.resolve({ data: makeJobsList({ running: true }) });
      return defaultGetImpl(url);
    });

    startFakeTimers();

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    await advanceTimersAndFlush(0);
    await advanceTimersAndFlush(0);

    const jobCallsInitial = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    await advanceTimersAndFlush(5000);

    const jobCallsAfter = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    expect(jobCallsAfter).toBeGreaterThan(jobCallsInitial);
  });

  it('does NOT poll /admin/jobs when no jobs are running', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/admin/jobs'))
        return Promise.resolve({
          data: { items: [], total: 0, limit: 20, offset: 0 },
        });
      return defaultGetImpl(url);
    });

    startFakeTimers();

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    await advanceTimersAndFlush(0);
    await advanceTimersAndFlush(0);

    const jobCallsInitial = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    await advanceTimersAndFlush(10000);

    const jobCallsAfter = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    expect(jobCallsAfter).toBe(jobCallsInitial);
  });
});

describe('CrawlerAdmin — Manual Run section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockImplementation(defaultGetImpl);
  });

  it('renders the Manual Run heading and the live-crawlers block', async () => {
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /manual run/i })
      ).toBeInTheDocument()
    );
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /live crawlers/i })
      ).toBeInTheDocument()
    );
    expect(
      screen.getByRole('heading', { name: /archive rescrape/i })
    ).toBeInTheDocument();
  });

  it('POSTs to /admin/crawlers/run when "Run all" is clicked', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        status: 'started',
        message: 'Crawler job started.',
        adapters: ['test-adapter'],
      },
    });

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    const runAllButton = await screen.findByRole('button', {
      name: /^run all$/i,
    });
    expect(runAllButton).toBeEnabled();
    runAllButton.click();

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/admin/crawlers/run',
        expect.objectContaining({
          adapters: ['all'],
          parallel: true,
        })
      )
    );
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/admin/crawlers/run',
      expect.objectContaining({
        crawler_default_category_id: '66666666-6666-7666-8666-666666666666',
      })
    );
  });

  it('POSTs to /admin/crawlers/rescrape-archives when "Rescrape latest archives" is clicked', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { status: 'started', message: 'Job queued.' },
    });

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    const rescrapeButton = await screen.findByRole('button', {
      name: /rescrape latest archives/i,
    });
    expect(rescrapeButton).toBeEnabled();
    rescrapeButton.click();

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/admin/crawlers/rescrape-archives',
        expect.objectContaining({
          default_category_id: '66666666-6666-7666-8666-666666666666',
        })
      )
    );
    const rescrapeCalls = vi
      .mocked(apiClient.post)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/crawlers/rescrape-archives')
      );
    expect(rescrapeCalls).toHaveLength(1);
  });
});
