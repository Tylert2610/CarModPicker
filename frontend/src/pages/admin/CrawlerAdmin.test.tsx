// Phase 8 plan 08-19 (D-07 + D-02) — page test for CrawlerAdmin.
//
// CrawlerAdmin.tsx (2,665 lines) is the largest page in the app and the FIRST
// use of vi.useFakeTimers() in the repo. Per RESEARCH.md §1 it is NOT a tabbed
// UI — it renders 4 sibling Card sections inside a CSS masonry (lines 1505,
// 1874, 2043, 2290). Tests mirror that structure with one describe block per
// section, plus an auth-gating describe block for the two early-return paths.
//
// Data flow: CrawlerAdmin imports `adminApi` from ../../api/admin and
// `categoriesApi` from ../../api/categories. Those modules internally call
// `apiClient` from ../../api/client, which setup.ts mocks globally. So each
// test stubs `apiClient.{get,post,patch,delete}` resolved values and lets the
// real adminApi / categoriesApi methods run normally.
//
// Per RESEARCH.md §1 + PATTERNS.md §12 Background Jobs section alone uses the
// fake-timer helpers from src/test/utils/async.ts (startFakeTimers,
// stopFakeTimers, advanceTimersAndFlush). We DO NOT call vi.useFakeTimers()
// directly — the helpers enforce Pitfall 5's `await act(...)` flush pattern.
//
// This task (Task 1) covers auth-gating + Sections 1 (Crawler Schedules) and
// 2 (Adapter Tuning). Sections 3 (Background Jobs) and 4 (Manual Run) land in
// follow-up tasks against the same file.

/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get) is the canonical Vitest pattern for typed mock
 * introspection. See Builder.test.tsx for the in-repo precedent.
 */

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

// Default GET routing used by the happy-path tests. Each branch matches the
// URL prefix that the corresponding adminApi / categoriesApi call issues.
// Order matters: `/admin/crawler-adapter-configs/` must match BEFORE
// `/admin/crawlers` so we don't accidentally hand the adapter-config endpoint
// the adapter catalog payload.
//
// Paths (from frontend/src/api/admin.ts):
//   /admin/crawler-schedules/              (list/create/reconcile)
//   /admin/crawler-adapter-configs/        (list/update tuning)
//   /admin/crawlers                        (list of adapter names + tiers)
//   /admin/crawlers/run                    (POST — manual run)
//   /admin/crawlers/rescrape-archives      (POST — rescrape)
//   /admin/jobs                            (background job list)
//   /crawled-pages/counts-by-source-and-status (status counts, optional)
//   /categories/                           (from categoriesApi)
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
    // Include an "other" category so fetchCrawlers auto-selects a
    // crawlerDefaultCategoryId — the Manual Run POST handlers short-circuit
    // with `setCrawlerError('Select a default category.')` otherwise.
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

// ─────────────────────────────────────────────────────────────────────────────
// describe blocks
// ─────────────────────────────────────────────────────────────────────────────

// Non-admin authenticated scenario — built from the canonical typed `mockUser`
// to avoid the stale shape in `testScenarios.authenticated.initialAuthState.user`
// (produced by `createMockUser()` which predates the is_service_account /
// subscription_tier / subscription_status / totp_enabled fields on UserRead).
// Mirrors the pattern from AdminDashboard.test.tsx.
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
    // The page header title confirms we fully rendered rather than bailing
    // into one of the auth-deny branches.
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
    // Confirm the schedules list endpoint was hit at least once.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/crawler-schedules/'
    );
    // And that the adapter-configs endpoint was hit as part of the initial
    // fan-out of four parallel fetchers in the mount useEffect.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/admin/crawler-adapter-configs/'
    );
    // Sanity: /admin/jobs/ (list) is also part of initial mount.
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
    // Use fireEvent over userEvent here: the async mount path starts several
    // parallel fetches, and userEvent's auto-flush can race with the still-
    // resolving initial POST mocks. fireEvent avoids that without changing
    // what we're asserting (the POST to /reconcile).
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
    // The subheading inside the card confirms the retailer-tuning grid
    // actually rendered (rather than the empty-state "no adapters" fallback).
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /per-retailer settings/i })
      ).toBeInTheDocument()
    );
  });

  it('issues a PATCH when an adapter delay select is changed', async () => {
    // Seed a single adapter so the tuning row is deterministically findable.
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

    // Wait for the tuning row to render, then pick the per-adapter delay select.
    // findByTitle returns HTMLElement; we narrow to HTMLSelectElement since
    // the component's <select> is the only element with title="Delay".
    const delayEl = await screen.findByTitle('Delay');
    const delaySelect = delayEl as HTMLSelectElement;
    // Initial value reflects the seeded adapter's delay_sec of 5.
    expect(delaySelect.value).toBe('5');
    // Directly fire a change event — simulates the user picking "10" (seconds).
    delaySelect.value = '10';
    delaySelect.dispatchEvent(new Event('change', { bubbles: true }));

    await waitFor(() =>
      expect(vi.mocked(apiClient.patch)).toHaveBeenCalledWith(
        '/admin/crawler-adapter-configs/test-adapter',
        expect.objectContaining({ delay_sec: 10 })
      )
    );
    // The PATCH was called exactly once — no stray duplicate dispatches.
    expect(vi.mocked(apiClient.patch)).toHaveBeenCalledTimes(1);
  });
});

describe('CrawlerAdmin — Background Jobs section', () => {
  // Per PATTERNS.md Gotcha #2 + Pitfall 5: the Background Jobs section owns
  // the fake-timer polling tests. IMPORTANT: we enable fake timers BEFORE
  // mount so the polling useEffect's setInterval(..., 5000) is registered
  // against the fake clock — a real setInterval would not be driven by
  // vi.advanceTimersByTime and the test would observe zero polling fetches
  // (Pitfall 5 variant). We explicitly do NOT call `waitFor` inside a
  // fake-timer test: @testing-library's waitFor uses an internal setInterval
  // retry loop which, under faked timers, never retries unless we advance
  // timers — that trap is easy to wander into, so we drive everything with
  // `advanceTimersAndFlush(...)` instead.
  //
  // afterEach always stops fake timers so a test that throws between
  // startFakeTimers and the advance step doesn't leak fake-timer state into
  // the next test.
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    stopFakeTimers();
  });

  it('renders the Background Jobs heading', async () => {
    vi.mocked(apiClient.get).mockImplementation(defaultGetImpl);
    // No fake timers here — just assert the heading renders under the
    // standard real-timer waitFor path.
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /background jobs/i })
      ).toBeInTheDocument()
    );
  });

  it('polls /admin/jobs every 5 s while a job is running', async () => {
    // Always return a running-job payload so the 5 s polling effect stays
    // mounted for the full test window.
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/admin/jobs'))
        return Promise.resolve({ data: makeJobsList({ running: true }) });
      return defaultGetImpl(url);
    });

    // Enable fake timers BEFORE mount so the polling useEffect's
    // setInterval(..., 5000) is registered against the fake clock.
    startFakeTimers();

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    // Flush the initial mount's promise chain so /admin/jobs resolves and
    // jobsList state settles into a running-job payload. advanceTimersAndFlush
    // wraps `vi.advanceTimersByTimeAsync` in `await act(...)`, which flushes
    // pending microtasks AND React's state batch — the polling useEffect
    // registers its 5 s setInterval inside this flush. We call it twice so
    // the second microtask pass catches any setState that scheduled a new
    // effect re-run.
    await advanceTimersAndFlush(0);
    await advanceTimersAndFlush(0);

    const jobCallsInitial = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    // Advance past the first 5 s poll tick. We expect at least one extra
    // /admin/jobs fetch from the setInterval callback.
    await advanceTimersAndFlush(5000);

    const jobCallsAfter = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    expect(jobCallsAfter).toBeGreaterThan(jobCallsInitial);
  });

  it('does NOT poll /admin/jobs when no jobs are running', async () => {
    // Return an empty jobs list so hasRunning === false and the poll effect
    // early-returns without scheduling a setInterval.
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/admin/jobs'))
        return Promise.resolve({
          data: { items: [], total: 0, limit: 20, offset: 0 },
        });
      return defaultGetImpl(url);
    });

    // Enable fake timers before mount — mirrors the "polls" test. If a
    // setInterval were registered under real timers (hypothetically a bug
    // in CrawlerAdmin), this test would still catch it because fake-timer
    // advancement doesn't drive real intervals → mock.calls.length would
    // stay equal either way. But symmetry with the positive test is more
    // important than catching that hypothetical.
    startFakeTimers();

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    await advanceTimersAndFlush(0);
    await advanceTimersAndFlush(0);

    const jobCallsInitial = vi
      .mocked(apiClient.get)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/jobs')
      ).length;

    // Advance well past the 5 s poll tick; no running job → no new fetch.
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
    // The Archive Rescrape subsection lives in the same Card.
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

    // Wait until the manual-run controls are available (default category
    // is auto-selected when the /categories response contains "other").
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
    // The run POST body must include the auto-picked default category id.
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

    // The default category id comes from defaultGetImpl's "other" seed.
    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/admin/crawlers/rescrape-archives',
        expect.objectContaining({
          default_category_id: '66666666-6666-7666-8666-666666666666',
        })
      )
    );
    // The rescrape endpoint should have been hit exactly once.
    const rescrapeCalls = vi
      .mocked(apiClient.post)
      .mock.calls.filter(([url]) =>
        String(url).startsWith('/admin/crawlers/rescrape-archives')
      );
    expect(rescrapeCalls).toHaveLength(1);
  });
});
