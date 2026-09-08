import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import PageHeader from '../../components/layout/PageHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { inputVariants } from '../../components/ui/input-variants';
import Spinner from '../../components/ui/spinner';
import type { BackgroundJob, BackgroundJobList, CrawlerAdapterConfig, CrawlerAdapterConfigUpdate, CrawlerJobProgress, CrawlerRunRequest, CrawlerRunResponse, CrawlerSchedule, CrawlerScheduleCreate, CrawlerScheduleUpdate, RescrapeArchivesQueuedResponse, RescrapeArchivesRequest } from '../../api/admin';
import { adminApi } from '../../api/admin';
import { categoriesApi } from '../../api/categories';
import type { CategoryResponse } from '../../types/Api';

// ── Fetcher-tier visual system ───────────────────────────────────────────
// Adapters declare a FETCHER_TIER on the backend; the UI groups them by
// blocking difficulty: T0 = plain HTTP, T1 = TLS impersonation, T2 = headless
// browser via FlareSolverr. T4 is a frontend-only override for newly-written
// adapters that haven't been smoke-tested yet — remove entries from
// UNVERIFIED_ADAPTERS as each one is validated.

type FetcherTier = 'http' | 'tls' | 'browser' | 'unverified';

// Phase 1 adapters (landed 2026-04-20) flagged as T4 = unverified until they
// pass a live smoke test. The backend still reports their real FETCHER_TIER
// (currently all "http"); this set only affects the UI grouping + chip. When
// an adapter has been confirmed to produce correct ScrapedPayload end-to-end
// on a real crawl, delete it from this set.
const UNVERIFIED_ADAPTERS: ReadonlySet<string> = new Set([
  // Inquiry-only brochure sites with no purchasable PDPs (no cart, no SKU,
  // no price — see each adapter's docstring). Crawl shape works but every
  // resulting Part row is a marketing stub. Hold T4 until a product-detection
  // story lands.
  'ecutek',
  'hennessey',
  'injectordynamics',
  // Stub adapters — no live storefront on any candidate host. Discovery
  // returns 0 URLs by design (see each adapter's docstring for recon).
  'jltperformance',
  'racerwholesale',
  'roadraceengineering',
  'stoptech',
  // Blanket robots.txt Disallow — adapter is for Chrome-extension capture
  // and archive rescrape only.
  'skunk2',
]);

const TIER_META: Record<
  FetcherTier,
  {
    label: string;
    full: string;
    badge: string;
    row: string;
    chipSelected: string;
    chipUnselected: string;
    dot: string;
  }
> = {
  http: {
    label: 'T0',
    full: 'Tier 0 — plain HTTP',
    badge: 'bg-success/40 border-success/60 text-success',
    row: 'border-l-2 border-l-success/70',
    chipSelected: 'border-success bg-success/40 text-success',
    chipUnselected: 'border-success/40 text-success/70 hover:border-success',
    dot: 'bg-success',
  },
  tls: {
    label: 'T1',
    full: 'Tier 1 — TLS impersonation (curl_cffi)',
    badge: 'bg-warning/40 border-warning/60 text-warning',
    row: 'border-l-2 border-l-warning/70',
    chipSelected: 'border-warning bg-warning/40 text-warning',
    chipUnselected: 'border-warning/40 text-warning/70 hover:border-warning',
    dot: 'bg-warning',
  },
  browser: {
    label: 'T2',
    full: 'Tier 2 — headless browser (FlareSolverr)',
    badge: 'bg-destructive/40 border-destructive/60 text-destructive',
    row: 'border-l-2 border-l-destructive/70',
    chipSelected: 'border-destructive bg-destructive/40 text-destructive',
    chipUnselected:
      'border-destructive/40 text-destructive/70 hover:border-destructive',
    dot: 'bg-destructive',
  },
  unverified: {
    label: 'T4',
    full: 'T4 — unverified: new adapter awaiting smoke test',
    badge: 'bg-info/40 border-info/60 text-info',
    row: 'border-l-2 border-l-info/70',
    chipSelected: 'border-info bg-info/40 text-info',
    chipUnselected: 'border-info/40 text-info/70 hover:border-info',
    dot: 'bg-info',
  },
};

function TierBadge({ tier }: { tier: FetcherTier | undefined }) {
  if (!tier) return null;
  const m = TIER_META[tier];
  return (
    <span
      title={m.full}
      className={`inline-flex items-center px-1 py-0 rounded text-[9px] font-semibold font-mono border ${m.badge}`}
    >
      {m.label}
    </span>
  );
}

// ── Job display helpers ──────────────────────────────────────────────────

/** Parse a server datetime string as UTC. Pydantic serialises naive datetimes
 *  without a timezone suffix, so JS would parse them as local time — causing a
 *  wrong offset equal to the user's UTC offset. Appending 'Z' forces UTC. */
function parseServerDate(s: string): Date {
  if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s + 'Z');
  }
  return new Date(s);
}

function fmtElapsed(startedAt: Date, endedAt?: Date | null): string {
  const ms = (endedAt ?? new Date()).getTime() - startedAt.getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

// Self-ticking elapsed-time display. Owns its own 1 s setInterval so the
// surrounding page does NOT re-render every second — only this leaf node
// updates. When `endedAt` is provided, the timer doesn't tick.
function ElapsedTimer({
  startedAt,
  endedAt,
  className,
}: {
  startedAt: Date;
  endedAt?: Date | null | undefined;
  className?: string | undefined;
}) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (endedAt) return;
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [endedAt]);
  return <span className={className}>{fmtElapsed(startedAt, endedAt)}</span>;
}

type UrlSample = {
  url: string;
  status?: number | string | null;
  bucket?: string | null;
  error?: string | null;
  source?: string | null;
  outcome?: string | null;
};

function UrlSampleList({
  items,
  max = 25,
}: {
  items: UrlSample[];
  max?: number;
}) {
  if (items.length === 0) return null;
  const shown = items.slice(0, max);
  const remainder = items.length - shown.length;
  return (
    <div className="divide-y divide-gray-800/60">
      {shown.map((entry, idx) => (
        <div
          // URLs can repeat across outcomes; composite with index keeps keys stable within one render.
          // eslint-disable-next-line react-x/no-array-index-key
          key={`${entry.url}-${entry.outcome ?? entry.bucket ?? ''}-${idx}`}
          className="py-1.5"
        >
          <div className="font-mono text-[11px] text-gray-300 break-all">
            {entry.url}
          </div>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {entry.source && (
              <span className="px-1 py-0 rounded text-[9px] font-mono bg-gray-800 text-gray-400 border border-gray-700">
                {entry.source}
              </span>
            )}
            {entry.outcome && (
              <span className="px-1 py-0 rounded text-[9px] font-mono bg-gray-800 text-gray-400 border border-gray-700">
                {entry.outcome}
              </span>
            )}
            {entry.status && (
              <span className="px-1 py-0 rounded text-[9px] font-mono bg-gray-800 text-gray-400 border border-gray-700">
                {entry.status}
              </span>
            )}
            {entry.bucket && (
              <span className="px-1 py-0 rounded text-[9px] font-mono bg-gray-800 text-gray-400 border border-gray-700">
                {entry.bucket}
              </span>
            )}
          </div>
          {entry.error && (
            <div className="mt-0.5 text-[10px] text-red-300 whitespace-pre-wrap break-all">
              {entry.error}
            </div>
          )}
        </div>
      ))}
      {remainder > 0 && (
        <div className="py-1 text-[10px] italic text-gray-500">
          …and {remainder} more.
        </div>
      )}
    </div>
  );
}

function CrawlerRunResult({ summary }: { summary: Record<string, unknown> }) {
  type AdapterResult = {
    adapter: string;
    ingested: number;
    skipped: number;
    skipped_not_product?: number;
    errors: number;
    total: number;
    error_urls?: UrlSample[];
    error_urls_truncated?: boolean;
    parse_miss_urls?: UrlSample[];
    parse_miss_urls_truncated?: boolean;
    rate_limit_bailout?: boolean;
    rate_limit_bailout_after?: number;
  };
  type FailedAdapter = { adapter: string; error: string };
  const totals = summary['summary'] as
    | {
        total_ingested?: number;
        total_skipped?: number;
        total_errors?: number;
      }
    | undefined;
  const results = (summary['results'] ?? []) as AdapterResult[];
  const failed = (summary['failed'] ?? []) as FailedAdapter[];
  const resultsWithFailures = results.filter(
    (r) =>
      (r.error_urls?.length ?? 0) > 0 || (r.parse_miss_urls?.length ?? 0) > 0
  );
  return (
    <div className="space-y-2">
      {totals && (
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-success/50 border border-success/60 text-xs text-success">
            <span className="font-semibold">{totals.total_ingested ?? 0}</span>{' '}
            ingested
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-800/60 border border-gray-600/60 text-xs text-gray-400">
            <span className="font-semibold">{totals.total_skipped ?? 0}</span>{' '}
            skipped
          </span>
          {(totals.total_errors ?? 0) > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-900/50 border border-red-700/60 text-xs text-red-300">
              <span className="font-semibold">{totals.total_errors}</span>{' '}
              errors
            </span>
          )}
        </div>
      )}
      {results.length > 0 && (
        <div className="rounded border border-gray-700/60 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700/60 bg-gray-900/50">
                <th className="text-left px-2 py-1 text-gray-500 font-medium">
                  Adapter
                </th>
                <th className="text-right px-2 py-1 text-gray-500 font-medium">
                  Total
                </th>
                <th className="text-right px-2 py-1 text-success/80 font-medium">
                  Ingested
                </th>
                <th className="text-right px-2 py-1 text-gray-500 font-medium">
                  Skipped
                </th>
                <th className="text-right px-2 py-1 text-red-500/80 font-medium">
                  Errors
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.adapter}
                  className="border-b border-gray-700/30 last:border-0"
                >
                  <td className="px-2 py-1 font-mono text-gray-300">
                    {r.adapter}
                    {r.rate_limit_bailout && (
                      <span
                        title="Rate-limit circuit breaker tripped"
                        className="ml-2 inline-block rounded bg-warning/60 border border-warning/60 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-warning"
                      >
                        Rate-limited @ {r.rate_limit_bailout_after ?? 0}/
                        {r.total}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1 text-right text-gray-400 tabular-nums">
                    {r.total}
                  </td>
                  <td className="px-2 py-1 text-right text-success tabular-nums font-medium">
                    {r.ingested}
                  </td>
                  <td className="px-2 py-1 text-right text-gray-400 tabular-nums">
                    {r.skipped}
                  </td>
                  <td
                    className={`px-2 py-1 text-right tabular-nums ${r.errors > 0 ? 'text-red-400 font-medium' : 'text-gray-600'}`}
                  >
                    {r.errors}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {resultsWithFailures.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-warning">
            Failure samples
          </p>
          {resultsWithFailures.map((r) => {
            const errTotal = r.errors;
            const missTotal = r.skipped_not_product ?? 0;
            const errSamples = r.error_urls ?? [];
            const missSamples = r.parse_miss_urls ?? [];
            return (
              <details
                key={r.adapter}
                className="rounded border border-gray-700/60 bg-gray-900/40 px-2 py-1 text-xs"
              >
                <summary className="cursor-pointer font-mono text-gray-200">
                  {r.adapter}{' '}
                  <span className="text-gray-500 font-sans">
                    — {errTotal} error(s), {missTotal} parse miss(es)
                  </span>
                </summary>
                <div className="mt-2 space-y-2">
                  {errSamples.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-red-400 mb-1">
                        Errors ({errTotal}
                        {r.error_urls_truncated ? '+' : ''})
                      </p>
                      <UrlSampleList items={errSamples} />
                    </div>
                  )}
                  {missSamples.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-warning mb-1">
                        Parse misses ({missTotal}
                        {r.parse_miss_urls_truncated ? '+' : ''})
                      </p>
                      <UrlSampleList items={missSamples} />
                    </div>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      )}
      {failed.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
            Failed adapters
          </p>
          {failed.map((f) => (
            <div
              key={f.adapter}
              className="rounded px-2 py-1 bg-red-950/40 border border-red-800/40 text-xs"
            >
              <span className="font-mono text-red-300">{f.adapter}</span>
              <span className="text-red-400/70 ml-2">{f.error}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ArchiveRescrapeProgress({
  summary,
  startedAt,
  endedAt,
}: {
  summary: Record<string, unknown> | null | undefined;
  startedAt: Date;
  endedAt?: Date | null | undefined;
}) {
  // Self-tick once per second so the rate display stays current while running.
  // Mirrors RunningCrawlerProgress — scoped to this subtree so the parent page
  // doesn't re-render every second.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (endedAt) return;
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [endedAt]);
  const processed = Number(summary?.['processed'] ?? 0);
  const total = Number(summary?.['total'] ?? 0);
  const hasTotal = total > 0;
  const pct = hasTotal
    ? Math.min(100, Math.max(0, Math.round((processed / total) * 100)))
    : 0;
  const ok = Number(summary?.['parsed_ok'] ?? 0);
  const failed =
    Number(summary?.['parse_failed'] ?? 0) +
    Number(summary?.['ingest_failed'] ?? 0);
  const elapsedSec = Math.max(
    0,
    Math.floor(((endedAt ?? new Date()).getTime() - startedAt.getTime()) / 1000)
  );
  const rateMinute =
    elapsedSec > 0 ? Math.round((processed / elapsedSec) * 60) : 0;
  // Rough ETA based on the trailing average rate. Hidden until we've actually
  // processed something — a zero-rate ETA is meaningless and just flashes.
  const remaining = hasTotal ? Math.max(0, total - processed) : 0;
  const etaSec =
    rateMinute > 0 && remaining > 0
      ? Math.round((remaining / rateMinute) * 60)
      : 0;
  const fmtEta = (s: number): string => {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r === 0 ? `${m}m` : `${m}m ${r}s`;
  };
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <div className="flex items-center gap-2 text-yellow-400/80">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-yellow-400" />
          </span>
          {hasTotal ? (
            <span>
              <span className="font-mono">
                {processed.toLocaleString()} / {total.toLocaleString()}
              </span>{' '}
              pages <span className="text-gray-500">· {pct}%</span>
            </span>
          ) : (
            <span>Queuing pages…</span>
          )}
        </div>
        <ElapsedTimer
          startedAt={startedAt}
          endedAt={endedAt}
          className="text-gray-500"
        />
      </div>
      <div className="h-1.5 w-full rounded bg-gray-800 overflow-hidden">
        <div
          className="h-full bg-success/80 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      {(hasTotal && (ok > 0 || failed > 0)) || rateMinute > 0 ? (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[10px] text-gray-400">
          {ok > 0 && (
            <span>
              <span className="text-success">{ok.toLocaleString()}</span> ok
            </span>
          )}
          {failed > 0 && (
            <span>
              <span className="text-red-400">{failed.toLocaleString()}</span>{' '}
              failed
            </span>
          )}
          {rateMinute > 0 && (
            <span>
              <span className="text-gray-500">rate</span>{' '}
              <span className="tabular-nums text-gray-200 font-semibold">
                {rateMinute.toLocaleString()}
              </span>
              <span className="text-gray-500">/min</span>
            </span>
          )}
          {!endedAt && etaSec > 0 && (
            <span>
              <span className="text-gray-500">eta</span>{' '}
              <span className="tabular-nums text-gray-200">
                {fmtEta(etaSec)}
              </span>
            </span>
          )}
        </div>
      ) : null}
    </div>
  );
}

function ArchiveRescrapeResult({
  summary,
  startedAt,
  endedAt,
}: {
  summary: Record<string, unknown>;
  startedAt?: Date;
  endedAt?: Date | null | undefined;
}) {
  const rows: { label: string; value: number; variant: string }[] = [
    {
      label: 'Parsed OK',
      value: Number(summary['parsed_ok'] ?? 0),
      variant: 'ok',
    },
    {
      label: 'Parse failed',
      value: Number(summary['parse_failed'] ?? 0),
      variant: 'err',
    },
    {
      label: 'Ingest failed',
      value: Number(summary['ingest_failed'] ?? 0),
      variant: 'err',
    },
    {
      label: 'No adapter',
      value: Number(summary['skipped_no_adapter'] ?? 0),
      variant: 'muted',
    },
    {
      label: 'No HTML',
      value: Number(summary['skipped_no_html'] ?? 0),
      variant: 'muted',
    },
  ];
  const failures = (summary['failures'] ?? []) as UrlSample[];
  const failuresTotal = Number(
    summary['failures_total'] ?? failures.length ?? 0
  );
  const truncated = Boolean(summary['failures_truncated']);
  // Wall-clock rate so post-run the operator can compare runs at a glance.
  // Falls back to processed when total isn't recorded (older summaries).
  const processedForRate = Number(
    summary['processed'] ?? summary['parsed_ok'] ?? 0
  );
  const elapsedSec =
    startedAt && endedAt
      ? Math.max(
          0,
          Math.floor((endedAt.getTime() - startedAt.getTime()) / 1000)
        )
      : 0;
  const rateMinute =
    elapsedSec > 0 && processedForRate > 0
      ? Math.round((processedForRate / elapsedSec) * 60)
      : 0;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {rows.map((r) => (
          <span
            key={r.label}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs ${
              r.value > 0 && r.variant === 'ok'
                ? 'bg-success/50 border-success/60 text-success'
                : r.value > 0 && r.variant === 'err'
                  ? 'bg-red-900/50 border-red-700/60 text-red-300'
                  : 'bg-gray-800/60 border-gray-600/60 text-gray-500'
            }`}
          >
            <span className="font-semibold">{r.value}</span> {r.label}
          </span>
        ))}
        {rateMinute > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-800/60 border border-gray-600/60 text-xs text-gray-300">
            <span className="font-semibold tabular-nums">
              {rateMinute.toLocaleString()}
            </span>
            <span className="text-gray-500">/min avg</span>
          </span>
        )}
      </div>
      {failures.length > 0 && (
        <details className="rounded border border-red-800/40 bg-red-950/20 px-2 py-1 text-xs">
          <summary className="cursor-pointer text-red-300">
            Failure samples{' '}
            <span className="text-red-400/70">
              ({failures.length}
              {truncated ? ` of ${failuresTotal}` : ''})
            </span>
          </summary>
          <div className="mt-2">
            <UrlSampleList items={failures} max={100} />
            {truncated && (
              <p className="text-[10px] text-gray-500 italic mt-1">
                Sample capped by worker; {failuresTotal - failures.length} more
                not shown.
              </p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function JobParams({ job }: { job: BackgroundJob }) {
  const p = job.params;
  if (!p) return null;
  if (job.job_type === 'crawler_run') {
    const adapters = (p['adapters'] as string[] | undefined) ?? [];
    const limits = (p['limits'] as Record<string, number> | undefined) ?? {};
    const globalLimit = p['global_limit'] as number | undefined;
    const delaySec = p['delay_sec'] as number | undefined;
    return (
      <div className="space-y-1.5">
        <div className="flex flex-wrap gap-1">
          {adapters.map((a) => (
            <span
              key={a}
              className="px-1.5 py-0.5 rounded bg-gray-800 border border-gray-600/60 font-mono text-xs text-gray-300"
            >
              {a}
              {limits[a] !== undefined && (
                <span className="ml-1 text-gray-500">×{limits[a]}</span>
              )}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
          {delaySec !== undefined && (
            <span>
              delay: <span className="text-gray-400">{delaySec}s</span>
            </span>
          )}
          {globalLimit !== undefined && (
            <span>
              global limit: <span className="text-gray-400">{globalLimit}</span>
            </span>
          )}
        </div>
      </div>
    );
  }
  return (
    <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
      {JSON.stringify(p, null, 2)}
    </pre>
  );
}

function jobInlineSummary(job: BackgroundJob): string | null {
  if (job.status === 'running') return null;
  const s = job.result_summary;
  if (!s) return null;
  if (job.job_type === 'crawler_run') {
    const totals = s['summary'] as
      { total_ingested?: number; total_errors?: number } | undefined;
    if (!totals) return null;
    const parts = [`${totals.total_ingested ?? 0} ingested`];
    if ((totals.total_errors ?? 0) > 0)
      parts.push(`${totals.total_errors} errors`);
    return parts.join(' · ');
  }
  if (job.job_type === 'archive_rescrape') {
    const ok = Number(s['parsed_ok'] ?? 0);
    const failed =
      Number(s['parse_failed'] ?? 0) + Number(s['ingest_failed'] ?? 0);
    const parts = [`${ok} parsed`];
    if (failed > 0) parts.push(`${failed} failed`);
    return parts.join(' · ');
  }
  return null;
}

function adapterProgressLabel(
  counts: Record<string, number> | undefined
): { parsed: number; total: number; tooltip: string } | null {
  if (!counts) return null;
  const parsed = counts['parsed'] ?? 0;
  const pending = counts['pending'] ?? 0;
  const gone = counts['gone'] ?? 0;
  const failed = counts['failed'] ?? 0;
  const total = parsed + pending + gone + failed;
  if (total === 0) return null;
  const tooltip = `parsed: ${parsed.toLocaleString()} · pending: ${pending.toLocaleString()} · gone: ${gone.toLocaleString()} · failed: ${failed.toLocaleString()}`;
  return { parsed, total, tooltip };
}

// Determine an adapter's target URL count for this run so we can draw a
// proportional progress bar. Falls back through per-adapter limit → global
// limit → the adapter's known catalog size (parsed + pending + gone).
function effectiveRunTarget(
  adapter: string,
  params: Record<string, unknown> | null,
  statusCounts: Record<string, number> | undefined
): number | null {
  const limits = (params?.['limits'] ?? {}) as Record<string, number | null>;
  const perAdapter = limits?.[adapter];
  if (typeof perAdapter === 'number' && perAdapter > 0) return perAdapter;
  const globalLimit = params?.['global_limit'];
  if (typeof globalLimit === 'number' && globalLimit > 0) return globalLimit;
  if (statusCounts) {
    const parsed = statusCounts['parsed'] ?? 0;
    const pending = statusCounts['pending'] ?? 0;
    const gone = statusCounts['gone'] ?? 0;
    const total = parsed + pending + gone;
    if (total > 0) return total;
  }
  return null;
}

// Classify per-adapter activity based on how recently last_parsed_at was
// updated vs the server-side `now` timestamp. Used to color-code rows and
// differentiate "actively working" from "probably done or queued".
type ActivityLevel = 'active' | 'idle' | 'stalled' | 'queued' | 'done';

function classifyActivity(
  lastParsedAt: string | null,
  serverNowIso: string,
  parsedThisRun: number,
  target: number | null
): ActivityLevel {
  if (target != null && parsedThisRun >= target && target > 0) return 'done';
  if (!lastParsedAt) return 'queued';
  const last = new Date(lastParsedAt).getTime();
  const now = new Date(serverNowIso).getTime();
  const ageSec = Math.max(0, (now - last) / 1000);
  if (ageSec < 15) return 'active';
  if (ageSec < 90) return 'idle';
  return 'stalled';
}

function formatAge(lastParsedAt: string | null, serverNowIso: string): string {
  if (!lastParsedAt) return '—';
  const last = new Date(lastParsedAt).getTime();
  const now = new Date(serverNowIso).getTime();
  const s = Math.max(0, Math.floor((now - last) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (m < 60) return rs > 0 ? `${m}m ${rs}s ago` : `${m}m ago`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm > 0 ? `${h}h ${rm}m ago` : `${h}h ago`;
}

const ACTIVITY_STYLES: Record<
  ActivityLevel,
  { dot: string; label: string; text: string }
> = {
  active: {
    dot: 'bg-success animate-pulse',
    label: 'active',
    text: 'text-success',
  },
  idle: { dot: 'bg-yellow-400', label: 'idle', text: 'text-yellow-400' },
  stalled: { dot: 'bg-orange-400', label: 'stalled', text: 'text-orange-400' },
  queued: { dot: 'bg-gray-500', label: 'queued', text: 'text-gray-400' },
  done: { dot: 'bg-success', label: 'done', text: 'text-success' },
};

function RunningCrawlerProgress({
  job,
  progress,
  statusCounts,
  startedAt,
}: {
  job: BackgroundJob;
  progress: CrawlerJobProgress | undefined;
  statusCounts: Record<string, Record<string, number>>;
  startedAt: Date;
}) {
  // Self-tick once per second so the rate display stays current. Scoped to
  // this subtree — the parent page does not re-render every second.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const elapsedSec = Math.max(
    0,
    Math.floor((Date.now() - startedAt.getTime()) / 1000)
  );
  const selected = ((job.params?.['adapters'] ?? []) as string[]) ?? [];
  const adaptersData = progress?.adapters ?? {};
  const serverNow = progress?.now ?? new Date().toISOString();

  // Totals across adapters.
  let parsedTotal = 0;
  let activeCount = 0;
  let doneCount = 0;
  const rows = selected.map((adapter) => {
    const d = adaptersData[adapter];
    const parsed = d?.parsed_this_run ?? 0;
    const target = effectiveRunTarget(
      adapter,
      job.params,
      statusCounts[adapter]
    );
    const last = d?.last_parsed_at ?? null;
    const activity = classifyActivity(last, serverNow, parsed, target);
    parsedTotal += parsed;
    if (activity === 'active') activeCount += 1;
    if (activity === 'done') doneCount += 1;
    return { adapter, parsed, target, last, activity };
  });

  const rateMinute =
    elapsedSec > 0 ? Math.round((parsedTotal / elapsedSec) * 60) : 0;

  // Sort: active first, then idle/stalled (things needing attention), then
  // queued, then done — operators want to see live action at the top.
  const order: Record<ActivityLevel, number> = {
    active: 0,
    idle: 1,
    stalled: 2,
    queued: 3,
    done: 4,
  };
  rows.sort(
    (a, b) =>
      order[a.activity] - order[b.activity] ||
      a.adapter.localeCompare(b.adapter)
  );

  return (
    <div className="space-y-2">
      {/* Summary strip */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-300">
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-yellow-400" />
          </span>
          <span className="text-yellow-400/80">Running</span>
        </span>
        <span>
          <span className="text-gray-500">active</span>{' '}
          <span className="tabular-nums text-success font-semibold">
            {activeCount}
          </span>
          <span className="text-gray-500"> / done </span>
          <span className="tabular-nums text-success font-semibold">
            {doneCount}
          </span>
          <span className="text-gray-500"> / total </span>
          <span className="tabular-nums text-gray-200 font-semibold">
            {selected.length}
          </span>
        </span>
        <span>
          <span className="text-gray-500">parsed</span>{' '}
          <span className="tabular-nums text-gray-100 font-semibold">
            {parsedTotal.toLocaleString()}
          </span>
        </span>
        <span>
          <span className="text-gray-500">rate</span>{' '}
          <span className="tabular-nums text-gray-100 font-semibold">
            {rateMinute.toLocaleString()}
          </span>
          <span className="text-gray-500">/min</span>
        </span>
      </div>

      {/* Per-adapter table */}
      {rows.length > 0 ? (
        <div className="border border-gray-700/60 rounded overflow-hidden">
          {rows.map(({ adapter, parsed, target, last, activity }) => {
            const pct =
              target && target > 0
                ? Math.min(100, (parsed / target) * 100)
                : parsed > 0
                  ? 100
                  : 0;
            const style = ACTIVITY_STYLES[activity];
            // Bar color shades with activity: green for healthy (active/done),
            // yellow/orange when falling behind, flat gray for queued.
            const barColor =
              activity === 'active' || activity === 'done'
                ? 'bg-success/70'
                : activity === 'idle'
                  ? 'bg-yellow-500/70'
                  : activity === 'stalled'
                    ? 'bg-orange-500/70'
                    : 'bg-gray-600/60';
            return (
              <div
                key={adapter}
                className="grid grid-cols-[9rem_1fr_8rem_5rem] items-center gap-2 px-2 py-1.5 border-b border-gray-700/40 last:border-b-0 odd:bg-gray-900/30"
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                  <span className="font-mono text-xs text-foreground truncate">
                    {adapter}
                  </span>
                </div>
                <div
                  className="relative h-2 rounded-sm bg-gray-800/80 overflow-hidden"
                  title={
                    target
                      ? `${parsed.toLocaleString()} / ${target.toLocaleString()} (${pct.toFixed(0)}%)`
                      : `${parsed.toLocaleString()} parsed (target unknown)`
                  }
                >
                  <div
                    className={`absolute inset-y-0 left-0 ${barColor}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="text-[11px] tabular-nums text-gray-300 text-right">
                  <span className="text-gray-100 font-semibold">
                    {parsed.toLocaleString()}
                  </span>
                  <span className="text-gray-500">
                    {' '}
                    / {target != null ? target.toLocaleString() : '?'}
                  </span>
                </div>
                <div
                  className={`text-[10px] tabular-nums ${style.text} text-right`}
                  title={
                    last
                      ? `last parsed ${new Date(last).toLocaleString()}`
                      : undefined
                  }
                >
                  {activity === 'queued'
                    ? 'queued'
                    : activity === 'done'
                      ? 'done'
                      : formatAge(last, serverNow)}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-gray-500">No adapters selected.</p>
      )}
    </div>
  );
}

// Self-buffered text input. Owns its own local state so keystrokes do NOT
// re-render the (very heavy) parent on each character. Commits the value to
// the parent only on blur or Enter. Used for inputs whose value isn't read
// reactively elsewhere on the page (e.g. the create-schedule name + the
// global crawler limit).
const LocalTextInput = memo(function LocalTextInput({
  initialValue,
  onCommit,
  className,
  type = 'text',
  placeholder,
  inputMode,
  min,
  id,
  inputKey,
}: {
  initialValue: string;
  onCommit: (value: string) => void;
  className?: string | undefined;
  type?: 'text' | 'number' | undefined;
  placeholder?: string | undefined;
  inputMode?: 'numeric' | 'text' | undefined;
  min?: string | undefined;
  id?: string | undefined;
  // Allow callers to force the input to re-sync with `initialValue` (e.g.
  // when a preset button writes a new value into parent state).
  inputKey?: string | number | undefined;
}) {
  const [value, setValue] = useState(initialValue);
  // Re-sync if the parent forces a new initialValue via inputKey change.
  const lastKeyRef = useRef(inputKey);
  if (lastKeyRef.current !== inputKey) {
    lastKeyRef.current = inputKey;
    if (value !== initialValue) setValue(initialValue);
  }
  return (
    <input
      id={id}
      type={type}
      inputMode={inputMode}
      min={min}
      value={value}
      placeholder={placeholder}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => {
        if (value !== initialValue) onCommit(value);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && value !== initialValue) {
          onCommit(value);
        }
      }}
      className={className}
    />
  );
});

const BackgroundJobItem = memo(function BackgroundJobItem({
  job,
  isExpanded,
  jobProgress,
  adapterStatusCounts,
  onToggleExpanded,
  onCancel,
}: {
  job: BackgroundJob;
  isExpanded: boolean;
  jobProgress: CrawlerJobProgress | undefined;
  adapterStatusCounts: Record<string, Record<string, number>>;
  onToggleExpanded: (id: string) => void;
  onCancel: (id: string) => void;
}) {
  const isRunning = job.status === 'running';
  const statusColor =
    job.status === 'completed'
      ? 'text-success'
      : job.status === 'failed'
        ? 'text-red-400'
        : isRunning
          ? 'text-yellow-400'
          : 'text-gray-400';
  const statusBg =
    job.status === 'completed'
      ? 'border-success/60 bg-success/30'
      : job.status === 'failed'
        ? 'border-red-800/60 bg-red-950/30'
        : isRunning
          ? 'border-yellow-800/60 bg-yellow-950/30'
          : 'border-gray-700 bg-gray-900/30';
  const typeLabel =
    job.job_type === 'crawler_run'
      ? 'Crawler Run'
      : job.job_type === 'archive_rescrape'
        ? 'Archive Rescrape'
        : job.job_type;
  const startedAt = parseServerDate(job.started_at);
  const completedAt = job.completed_at
    ? parseServerDate(job.completed_at)
    : null;
  const inlineSummary = jobInlineSummary(job);
  return (
    <div className={`rounded-lg border text-sm ${statusBg}`}>
      {isRunning && (
        <div className="h-0.5 w-full rounded-t-lg overflow-hidden bg-yellow-950/50">
          <div className="h-full bg-yellow-400/70 animate-[progress-indeterminate_1.8s_ease-in-out_infinite] w-1/3" />
        </div>
      )}
      <div className="px-2 py-1">
        <button
          className="w-full flex items-center justify-between gap-2 text-left"
          onClick={() => onToggleExpanded(job.id)}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            {isRunning ? (
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-400" />
              </span>
            ) : null}
            <span
              className={`font-semibold text-[10px] uppercase tracking-wide shrink-0 ${statusColor}`}
            >
              {job.status}
            </span>
            <span className="text-xs text-gray-300 font-medium truncate">
              #{job.id} — {typeLabel}
            </span>
            <span className="text-gray-500 text-[10px] shrink-0">
              {job.triggered_by}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0 text-[11px] text-gray-400">
            {inlineSummary && (
              <span
                className={`tabular-nums ${job.status === 'failed' ? 'text-red-400/70' : 'text-gray-400'}`}
              >
                {inlineSummary}
              </span>
            )}
            <ElapsedTimer
              startedAt={startedAt}
              endedAt={completedAt}
              className={`tabular-nums ${isRunning ? 'text-yellow-400/80' : ''}`}
            />
            <span className="text-gray-600">{isExpanded ? '▲' : '▼'}</span>
          </div>
        </button>

        {isExpanded && (
          <div className="mt-2 pt-2 border-t border-gray-700/60 space-y-3">
            <p className="text-xs text-gray-500">
              Started {startedAt.toLocaleString()}
              {completedAt && <> · Finished {completedAt.toLocaleString()}</>}
            </p>

            {job.params && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                  Parameters
                </p>
                <JobParams job={job} />
              </div>
            )}

            {isRunning && job.job_type === 'crawler_run' && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                  Live progress
                </p>
                <RunningCrawlerProgress
                  job={job}
                  progress={jobProgress}
                  statusCounts={adapterStatusCounts}
                  startedAt={startedAt}
                />
              </div>
            )}
            {isRunning && job.job_type === 'archive_rescrape' && (
              <ArchiveRescrapeProgress
                summary={job.result_summary}
                startedAt={startedAt}
                endedAt={completedAt}
              />
            )}
            {isRunning &&
              job.job_type !== 'crawler_run' &&
              job.job_type !== 'archive_rescrape' && (
                <div className="flex items-center gap-2 text-xs text-yellow-400/80">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-yellow-400" />
                  </span>
                  Running for{' '}
                  <ElapsedTimer startedAt={startedAt} endedAt={completedAt} /> —
                  results will appear when the job completes
                </div>
              )}

            {job.result_summary &&
              !(isRunning && job.job_type === 'archive_rescrape') && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
                    Result
                  </p>
                  {job.job_type === 'crawler_run' ? (
                    <CrawlerRunResult summary={job.result_summary} />
                  ) : job.job_type === 'archive_rescrape' ? (
                    <ArchiveRescrapeResult
                      summary={job.result_summary}
                      startedAt={startedAt}
                      endedAt={completedAt}
                    />
                  ) : (
                    <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                      {JSON.stringify(job.result_summary, null, 2)}
                    </pre>
                  )}
                </div>
              )}

            {job.error_message && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500 mb-1">
                  Error
                </p>
                <pre className="text-xs text-red-300 bg-red-950/40 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                  {job.error_message}
                </pre>
              </div>
            )}

            {isRunning && (
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => onCancel(job.id)}
                  className="text-xs text-red-400 hover:text-red-300 underline"
                >
                  Cancel job
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

const BackgroundJobsCard = memo(function BackgroundJobsCard({
  jobsList,
  isLoadingJobs,
  expandedJobId,
  jobProgress,
  adapterStatusCounts,
  onToggleExpanded,
  onCancel,
}: {
  jobsList: BackgroundJobList | null;
  isLoadingJobs: boolean;
  expandedJobId: string | null;
  jobProgress: Record<string, CrawlerJobProgress>;
  adapterStatusCounts: Record<string, Record<string, number>>;
  onToggleExpanded: (id: string) => void;
  onCancel: (id: string) => void;
}) {
  return (
    <Card padding="sm">
      <div className="mb-2">
        <h2 className="text-base font-semibold text-white leading-tight">
          Background Jobs
        </h2>
        <p className="text-[11px] text-gray-400">
          Polls every 5 s while a job is running.
          {jobsList ? ` · ${jobsList.total} total` : ''}
        </p>
      </div>

      {!jobsList && isLoadingJobs && (
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      )}

      {jobsList && jobsList.items.length === 0 && (
        <p className="text-xs text-gray-500 text-center py-4">No jobs yet.</p>
      )}

      {jobsList && jobsList.items.length > 0 && (
        <div className="space-y-1.5">
          {jobsList.items.map((job: BackgroundJob) => (
            <BackgroundJobItem
              key={job.id}
              job={job}
              isExpanded={expandedJobId === job.id}
              jobProgress={jobProgress[job.id]}
              adapterStatusCounts={adapterStatusCounts}
              onToggleExpanded={onToggleExpanded}
              onCancel={onCancel}
            />
          ))}
        </div>
      )}
    </Card>
  );
});

// Wrapper around the Live Crawlers per-adapter row list. Memoized so that
// re-renders of CrawlerAdmin caused by unrelated state (e.g. typing into a
// schedule name) do NOT re-execute the 100-row map + 100 createElement
// calls. Each LiveCrawlerRow inside is also memoized; together they collapse
// the cost of unrelated re-renders to ~zero for this list.
const LiveCrawlerRowList = memo(function LiveCrawlerRowList({
  sortedAdapters,
  adapterTiers,
  selectedCrawlers,
  crawlerLimits,
  adapterStatusCounts,
  onToggleSelected,
  onLimitChange,
}: {
  sortedAdapters: readonly string[];
  adapterTiers: Record<string, FetcherTier>;
  selectedCrawlers: Set<string>;
  crawlerLimits: Record<string, string>;
  adapterStatusCounts: Record<string, Record<string, number>>;
  onToggleSelected: (adapter: string) => void;
  onLimitChange: (adapter: string, value: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1 mb-2">
      {sortedAdapters.map((adapter) => (
        <LiveCrawlerRow
          key={adapter}
          adapter={adapter}
          tier={adapterTiers[adapter]}
          selected={selectedCrawlers.has(adapter)}
          limitValue={crawlerLimits[adapter] ?? ''}
          statusCounts={adapterStatusCounts[adapter]}
          onToggleSelected={onToggleSelected}
          onLimitChange={onLimitChange}
        />
      ))}
    </div>
  );
});

// ── Memoized whole-section components ────────────────────────────────────
// Extracted so unrelated parent state changes (e.g. typing into the New
// Schedule name input) don't re-execute these sections' JSX. Each takes a
// stable set of props; React.memo skips re-render when none change.

const AdapterTuningCard = memo(function AdapterTuningCard({
  isLoadingConfigs,
  adapterConfigs,
  sortedAdapterConfigs,
  adapterTiers,
  savingConfigName,
  adapterStatusCounts,
  crawlerCategories,
  configSaveError,
  onSave,
}: {
  isLoadingConfigs: boolean;
  adapterConfigs: CrawlerAdapterConfig[];
  sortedAdapterConfigs: CrawlerAdapterConfig[];
  adapterTiers: Record<string, FetcherTier>;
  savingConfigName: string | null;
  adapterStatusCounts: Record<string, Record<string, number>>;
  crawlerCategories: CategoryResponse[];
  configSaveError: string | null;
  onSave: (
    adapterName: string,
    patch: CrawlerAdapterConfigUpdate
  ) => void | Promise<void>;
}) {
  return (
    <Card padding="sm">
      <h2 className="text-base font-semibold text-white leading-tight">
        Adapter Tuning
      </h2>
      <p className="text-xs text-muted-foreground mb-2">
        Per-retailer delay, run limit, and default category. Applies on the next
        scheduled run — no AWS sync needed.
      </p>

      {configSaveError && (
        <div className="mb-2">
          <ErrorAlert message={configSaveError} />
        </div>
      )}

      {isLoadingConfigs && adapterConfigs.length === 0 ? (
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      ) : adapterConfigs.length === 0 ? (
        <p className="text-xs text-gray-500 py-2">
          No adapters registered yet.
        </p>
      ) : (
        <div className="p-2 bg-blue-900/10 border border-blue-700/60 rounded-lg">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-blue-200 mb-2">
            Per-retailer settings
          </h3>
          <div className="grid grid-cols-1 gap-1">
            {sortedAdapterConfigs.map((row) => (
              <AdapterTuningRow
                key={row.id}
                row={row}
                tier={adapterTiers[row.adapter_name]}
                isSaving={savingConfigName === row.adapter_name}
                statusCounts={adapterStatusCounts[row.adapter_name]}
                categories={crawlerCategories}
                onSave={onSave}
              />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
});

// ── Memoized per-adapter row components ──────────────────────────────────
// These lists render ~100 rows each in three+ sections. Without memoization,
// a single keystroke into ANY controlled input on the page (e.g. a schedule
// name, a global limit, or one adapter's per-run limit) re-renders the entire
// CrawlerAdmin tree, which is hundreds of inputs and buttons. Memoizing each
// row + stabilising the per-row callbacks keeps keystroke cost O(1).

const TIER_SORT_ORDER: Record<FetcherTier, number> = {
  http: 0,
  tls: 1,
  browser: 2,
  unverified: 4,
};

function sortAdaptersByTier(
  names: readonly string[],
  tiers: Record<string, FetcherTier>
): string[] {
  return [...names].sort((a, b) => {
    const ta = tiers[a];
    const tb = tiers[b];
    const da = ta ? TIER_SORT_ORDER[ta] : 3;
    const db = tb ? TIER_SORT_ORDER[tb] : 3;
    if (da !== db) return da - db;
    return a.localeCompare(b);
  });
}

const LiveCrawlerRow = memo(function LiveCrawlerRow({
  adapter,
  tier,
  selected,
  limitValue,
  statusCounts,
  onToggleSelected,
  onLimitChange,
}: {
  adapter: string;
  tier: FetcherTier | undefined;
  selected: boolean;
  limitValue: string;
  statusCounts: Record<string, number> | undefined;
  onToggleSelected: (adapter: string) => void;
  onLimitChange: (adapter: string, value: string) => void;
}) {
  const tierRow = tier ? TIER_META[tier].row : '';
  const progress = adapterProgressLabel(statusCounts);
  return (
    <div
      className={`flex items-center gap-1.5 py-0.5 pl-2 pr-1 bg-gray-800/50 rounded border border-gray-700 ${tierRow}`}
    >
      <label className="flex items-center gap-1.5 cursor-pointer flex-1 min-w-0">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelected(adapter)}
          className="h-3.5 w-3.5 rounded border-gray-600 bg-gray-700 text-success focus:ring-success"
        />
        <TierBadge tier={tier} />
        <span className="font-mono text-xs text-foreground truncate">
          {adapter}
        </span>
      </label>
      {progress ? (
        <span
          title={progress.tooltip}
          className="shrink-0 tabular-nums text-[10px] px-1 py-0.5 rounded bg-gray-700/60 border border-gray-600/50 text-gray-400 font-mono"
        >
          {progress.parsed.toLocaleString()}
          <span className="text-gray-500">{' / '}</span>
          {progress.total.toLocaleString()}
        </span>
      ) : null}
      <input
        type="number"
        min="1"
        placeholder="—"
        defaultValue={limitValue}
        onBlur={(e) => onLimitChange(adapter, e.target.value)}
        className="w-12 px-1 py-0.5 text-xs text-center rounded border border-white/20 bg-gray-800 text-foreground focus:border-success focus:outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
      />
    </div>
  );
});

const AdapterTuningRow = memo(function AdapterTuningRow({
  row,
  tier,
  isSaving,
  statusCounts,
  categories,
  onSave,
}: {
  row: CrawlerAdapterConfig;
  tier: FetcherTier | undefined;
  isSaving: boolean;
  statusCounts: Record<string, number> | undefined;
  categories: CategoryResponse[];
  onSave: (
    adapterName: string,
    patch: CrawlerAdapterConfigUpdate
  ) => void | Promise<void>;
}) {
  const tierRow = tier ? TIER_META[tier].row : '';
  const progress = adapterProgressLabel(statusCounts);
  return (
    <div
      className={`flex flex-wrap items-center gap-1.5 py-1 pl-2 pr-1 bg-gray-800/50 rounded border border-gray-700 ${tierRow}`}
    >
      <TierBadge tier={tier} />
      <span className="font-mono text-xs text-foreground truncate min-w-[5rem] flex-1">
        {row.adapter_name}
      </span>
      {progress ? (
        <span
          title={progress.tooltip}
          className="shrink-0 tabular-nums text-[10px] px-1.5 py-0.5 rounded bg-gray-700/60 border border-gray-600/50 text-gray-400 font-mono"
        >
          {progress.parsed.toLocaleString()}
          <span className="text-gray-500">{' / '}</span>
          {progress.total.toLocaleString()}
        </span>
      ) : null}
      <select
        id={`tune-delay-${row.adapter_name}`}
        title="Delay"
        value={String(row.delay_sec)}
        onChange={(e) =>
          void onSave(row.adapter_name, {
            delay_sec: Number(e.target.value),
          })
        }
        disabled={isSaving}
        className="bg-gray-800 border border-gray-600 rounded px-1 py-0.5 text-xs text-gray-100 focus:outline-none focus:border-blue-500 disabled:opacity-50"
      >
        {[2.5, 5, 10, 15, 30].map((v) => (
          <option key={v} value={String(v)}>
            {v}s
          </option>
        ))}
      </select>
      <Input
        id={`tune-limit-${row.adapter_name}`}
        key={`tune-limit-${row.adapter_name}-${row.per_run_limit ?? 'none'}`}
        type="number"
        min="1"
        defaultValue={
          row.per_run_limit == null ? '' : String(row.per_run_limit)
        }
        placeholder="∞"
        onBlur={(e) => {
          const raw = e.target.value.trim();
          if (raw === '') {
            if (row.per_run_limit != null) {
              void onSave(row.adapter_name, {
                clear_per_run_limit: true,
              });
            }
          } else {
            const n = Number(raw);
            if (Number.isFinite(n) && n >= 1 && n !== row.per_run_limit) {
              void onSave(row.adapter_name, { per_run_limit: n });
            }
          }
        }}
        disabled={isSaving}
        className="w-14 min-h-0 py-0.5 text-xs"
      />
      <label
        title="Skip URLs already archived as parsed"
        className="inline-flex items-center gap-1 text-[11px] text-gray-300"
      >
        <input
          type="checkbox"
          checked={row.skip_known_urls}
          onChange={(e) =>
            void onSave(row.adapter_name, {
              skip_known_urls: e.target.checked,
            })
          }
          disabled={isSaving}
          className="h-3 w-3 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
        />
        skip
      </label>
      <select
        id={`tune-cat-${row.adapter_name}`}
        title="Default category for new parts"
        value={row.default_category_id}
        onChange={(e) =>
          void onSave(row.adapter_name, {
            default_category_id: e.target.value,
          })
        }
        disabled={isSaving || categories.length === 0}
        className="bg-gray-800 border border-gray-600 rounded px-1 py-0.5 text-xs text-gray-100 focus:outline-none focus:border-blue-500 disabled:opacity-50 max-w-[8rem]"
      >
        {categories.map((c) => (
          <option key={c.id} value={String(c.id)}>
            {c.name}
          </option>
        ))}
      </select>
    </div>
  );
});

// Compact selected-only adapter picker for a schedule. Renders ONLY the
// adapters this schedule already includes (typically <20) as removable
// chips, plus a native <select> to add unselected adapters. Replaces the
// previous "render all 100 adapters as chips" UI which was the page's
// dominant render cost.
const ScheduleAdapterPicker = memo(function ScheduleAdapterPicker({
  row,
  sortedAdapters,
  adapterTiers,
  isSaving,
  onToggle,
}: {
  row: CrawlerSchedule;
  sortedAdapters: readonly string[];
  adapterTiers: Record<string, FetcherTier>;
  isSaving: boolean;
  onToggle: (row: CrawlerSchedule, name: string) => void | Promise<void>;
}) {
  const memberNames = useMemo(
    () => new Set(row.adapters.map((a) => a.adapter_name)),
    [row.adapters]
  );
  // Adapters the user can add — sorted by tier already, just filter.
  const unselectedSorted = useMemo(
    () => sortedAdapters.filter((name) => !memberNames.has(name)),
    [sortedAdapters, memberNames]
  );
  // Selected chips, also kept in tier order for visual consistency.
  const selectedSorted = useMemo(
    () => sortedAdapters.filter((name) => memberNames.has(name)),
    [sortedAdapters, memberNames]
  );
  const handleRemove = useCallback(
    (name: string) => void onToggle(row, name),
    [onToggle, row]
  );
  const handleAdd = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const name = e.target.value;
      if (!name) return;
      void onToggle(row, name);
      // Reset select so the same option can be added again immediately
      // after another remove + re-add cycle.
      e.target.value = '';
    },
    [onToggle, row]
  );
  return (
    <div className="space-y-1.5">
      {selectedSorted.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedSorted.map((name) => {
            const tier = adapterTiers[name];
            const cls = tier
              ? TIER_META[tier].chipSelected
              : 'border-success bg-success/40 text-success';
            return (
              <span
                key={name}
                className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-mono ${cls}`}
              >
                {name}
                <button
                  type="button"
                  onClick={() => handleRemove(name)}
                  disabled={isSaving}
                  title="Remove"
                  className="text-current/70 hover:text-current disabled:opacity-50"
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}
      {unselectedSorted.length > 0 && (
        <select
          value=""
          onChange={handleAdd}
          disabled={isSaving}
          className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono focus:outline-none focus:border-blue-500 disabled:opacity-50"
        >
          <option value="">+ Add adapter…</option>
          {unselectedSorted.map((name) => {
            const tier = adapterTiers[name];
            const tierLabel = tier ? TIER_META[tier].label : '?';
            return (
              <option key={name} value={name}>
                {tierLabel} · {name}
              </option>
            );
          })}
        </select>
      )}
    </div>
  );
});

// Compact selected-only adapter picker for the New Schedule form. Same
// pattern as ScheduleAdapterPicker but operates on the local selection
// array rather than a saved schedule.
const NewScheduleAdapterPicker = memo(function NewScheduleAdapterPicker({
  selected,
  sortedAdapters,
  adapterTiers,
  onToggle,
}: {
  selected: readonly string[];
  sortedAdapters: readonly string[];
  adapterTiers: Record<string, FetcherTier>;
  onToggle: (name: string) => void;
}) {
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const unselectedSorted = useMemo(
    () => sortedAdapters.filter((n) => !selectedSet.has(n)),
    [sortedAdapters, selectedSet]
  );
  const selectedSorted = useMemo(
    () => sortedAdapters.filter((n) => selectedSet.has(n)),
    [sortedAdapters, selectedSet]
  );
  const handleAdd = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const name = e.target.value;
      if (!name) return;
      onToggle(name);
      e.target.value = '';
    },
    [onToggle]
  );
  return (
    <div className="space-y-1.5">
      {selectedSorted.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedSorted.map((name) => {
            const tier = adapterTiers[name];
            const cls = tier
              ? TIER_META[tier].chipSelected
              : 'border-success bg-success/40 text-success';
            return (
              <span
                key={name}
                className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full border font-mono ${cls}`}
              >
                {name}
                <button
                  type="button"
                  onClick={() => onToggle(name)}
                  title="Remove"
                  className="text-current/70 hover:text-current"
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}
      {unselectedSorted.length > 0 && (
        <select
          value=""
          onChange={handleAdd}
          className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono focus:outline-none focus:border-blue-500"
        >
          <option value="">+ Add adapter…</option>
          {unselectedSorted.map((name) => {
            const tier = adapterTiers[name];
            const tierLabel = tier ? TIER_META[tier].label : '?';
            return (
              <option key={name} value={name}>
                {tierLabel} · {name}
              </option>
            );
          })}
        </select>
      )}
    </div>
  );
});

// Module-level pure lookup so it's not re-created per render and can be
// shared by ScheduleRow + SchedulesCard without prop-drilling a callback.
function presetForExpression(
  expression: string,
  presets: Record<string, string>
): string {
  for (const [name, expr] of Object.entries(presets)) {
    if (expr === expression) return name;
  }
  return 'custom';
}

// ── New schedule form ────────────────────────────────────────────────────
// State lives here so typing into the name input only re-renders this small
// form, NOT the surrounding SchedulesCard (which would in turn reconcile
// every existing schedule row).
const NewScheduleForm = memo(function NewScheduleForm({
  sortedAdapters,
  adapterTiers,
  onCreate,
}: {
  sortedAdapters: readonly string[];
  adapterTiers: Record<string, FetcherTier>;
  onCreate: (body: CrawlerScheduleCreate) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [preset, setPreset] = useState<
    'monthly' | 'weekly' | 'daily' | 'custom'
  >('monthly');
  const [customExpression, setCustomExpression] = useState('');
  const [adapters, setAdapters] = useState<string[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleAdapter = useCallback((n: string) => {
    setAdapters((prev) =>
      prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n]
    );
  }, []);

  const handleSubmit = useCallback(async () => {
    const trimmedName = name.trim();
    if (!trimmedName) return;
    setIsCreating(true);
    setError(null);
    const body: CrawlerScheduleCreate = {
      name: trimmedName,
      enabled: false,
      adapters,
      ...(preset === 'custom'
        ? { schedule_expression: customExpression.trim() }
        : { preset }),
    };
    try {
      await onCreate(body);
      setName('');
      setPreset('monthly');
      setCustomExpression('');
      setAdapters([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create schedule.');
    } finally {
      setIsCreating(false);
    }
  }, [name, preset, customExpression, adapters, onCreate]);

  return (
    <div className="mb-2 p-2 rounded border border-dashed border-gray-700 bg-gray-900/30">
      <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400 mb-1.5">
        New schedule
      </p>
      {error && (
        <div className="mb-1.5">
          <ErrorAlert message={error} />
        </div>
      )}
      <div className="space-y-1.5">
        <Input
          id="new-schedule-name"
          placeholder="e.g. retailers-daily"
          value={name}
          onChange={(e) =>
            setName(
              e.target.value
                .toLowerCase()
                .replace(/[^a-z0-9-]+/g, '-')
                .replace(/^-+/, '')
                .slice(0, 26)
            )
          }
        />
        <div className="flex flex-wrap gap-1">
          {(['monthly', 'weekly', 'daily', 'custom'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={`px-2 py-0.5 text-[11px] rounded-full border transition-colors ${
                preset === p
                  ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                  : 'border-gray-600 text-gray-400 hover:border-gray-400'
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
        {preset === 'custom' && (
          <LocalTextInput
            type="text"
            initialValue={customExpression}
            onCommit={setCustomExpression}
            placeholder="cron(0 2 1 * ? *)"
            className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500"
          />
        )}
        <NewScheduleAdapterPicker
          selected={adapters}
          sortedAdapters={sortedAdapters}
          adapterTiers={adapterTiers}
          onToggle={toggleAdapter}
        />
        <Button
          onClick={() => void handleSubmit()}
          disabled={
            isCreating ||
            !name.trim() ||
            adapters.length === 0 ||
            (preset === 'custom' && !customExpression.trim())
          }
          className="bg-blue-600 hover:bg-blue-700 text-white text-[11px] py-0.5 px-2.5"
        >
          {isCreating ? 'Creating…' : 'Create schedule'}
        </Button>
      </div>
    </div>
  );
});

// ── Schedule row ─────────────────────────────────────────────────────────
// Memoized per-row so a state change in one row (e.g. typing into row A's
// custom-cron field) doesn't reconcile rows B, C, D… With ~10+ schedules
// this is the difference between snappy and laggy interactions.
type ScheduleDraft = { preset: string; customExpression: string };

const ScheduleRow = memo(function ScheduleRow({
  row,
  draftPreset,
  draftCustomExpression,
  originalPreset,
  presetExpressions,
  sortedAdapters,
  adapterTiers,
  isExpanded,
  isSaving,
  onToggleExpanded,
  onSetDraft,
  onSave,
  onDelete,
  onToggleAdapter,
}: {
  row: CrawlerSchedule;
  draftPreset: string;
  draftCustomExpression: string;
  originalPreset: string;
  presetExpressions: Record<string, string>;
  sortedAdapters: readonly string[];
  adapterTiers: Record<string, FetcherTier>;
  isExpanded: boolean;
  isSaving: boolean;
  onToggleExpanded: (id: string) => void;
  onSetDraft: (id: string, draft: ScheduleDraft) => void;
  onSave: (id: string, patch: CrawlerScheduleUpdate) => Promise<void> | void;
  onDelete: (row: CrawlerSchedule) => Promise<void> | void;
  onToggleAdapter: (row: CrawlerSchedule, name: string) => Promise<void> | void;
}) {
  const reconcileFailed = !!row.last_reconcile_error;
  const handleCustomCommit = useCallback(
    (v: string) => {
      onSetDraft(row.id, { preset: 'custom', customExpression: v });
    },
    [row.id, onSetDraft]
  );
  return (
    <div className="p-2 rounded border border-gray-700 bg-gray-900/40">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onToggleExpanded(row.id)}
          className="flex-1 min-w-0 text-left flex items-center gap-2"
        >
          <span className="text-gray-500 text-[10px] shrink-0">
            {isExpanded ? '▲' : '▼'}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-gray-100 font-mono truncate">
              {row.name}
            </p>
            <p className="text-[10px] text-gray-500 truncate">
              {row.enabled ? (
                <span className="text-success">Enabled</span>
              ) : (
                <span>Disabled</span>
              )}
              {' · '}
              <span className="font-mono">{row.schedule_expression}</span>
              {' · '}
              <span>{row.adapters.length} adapter(s)</span>
            </p>
          </div>
        </button>
        <button
          onClick={() => void onSave(row.id, { enabled: !row.enabled })}
          disabled={isSaving}
          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
            row.enabled ? 'bg-success' : 'bg-gray-600'
          }`}
          title={row.enabled ? 'Disable' : 'Enable'}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
              row.enabled ? 'translate-x-4' : 'translate-x-0'
            }`}
          />
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-2 mt-2">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400 mb-1">
              Adapters ({row.adapters.length})
            </p>
            <ScheduleAdapterPicker
              row={row}
              sortedAdapters={sortedAdapters}
              adapterTiers={adapterTiers}
              isSaving={isSaving}
              onToggle={onToggleAdapter}
            />
          </div>

          <div>
            <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400 mb-1">
              Interval
            </p>
            <div className="flex flex-wrap gap-1">
              {(['monthly', 'weekly', 'daily'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() =>
                    onSetDraft(row.id, { preset: p, customExpression: '' })
                  }
                  className={`px-2 py-0.5 text-[11px] rounded-full border transition-colors ${
                    draftPreset === p
                      ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                      : 'border-gray-600 text-gray-400 hover:border-gray-400'
                  }`}
                >
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
              <button
                onClick={() =>
                  onSetDraft(row.id, {
                    preset: 'custom',
                    customExpression:
                      draftCustomExpression || row.schedule_expression,
                  })
                }
                className={`px-2 py-0.5 text-[11px] rounded-full border transition-colors ${
                  draftPreset === 'custom'
                    ? 'border-blue-500 bg-blue-900/40 text-blue-300'
                    : 'border-gray-600 text-gray-400 hover:border-gray-400'
                }`}
              >
                Custom
              </button>
            </div>
            {draftPreset === 'custom' && (
              <LocalTextInput
                type="text"
                initialValue={draftCustomExpression}
                inputKey={row.id}
                onCommit={handleCustomCommit}
                placeholder="cron(0 2 1 * ? *)"
                className="mt-1 w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
            )}
            {draftPreset !== 'custom' && presetExpressions[draftPreset] && (
              <p className="text-[10px] text-gray-500 font-mono mt-0.5">
                {presetExpressions[draftPreset]}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {draftPreset === 'custom' || originalPreset !== draftPreset ? (
              <Button
                onClick={() =>
                  void onSave(
                    row.id,
                    draftPreset === 'custom'
                      ? { schedule_expression: draftCustomExpression }
                      : {
                          preset: draftPreset as 'monthly' | 'weekly' | 'daily',
                        }
                  )
                }
                disabled={
                  isSaving ||
                  (draftPreset === 'custom' && !draftCustomExpression.trim())
                }
                className="bg-blue-600 hover:bg-blue-700 text-white text-[11px] py-0.5 px-2.5"
              >
                {isSaving ? 'Saving…' : 'Save interval'}
              </Button>
            ) : null}
            <button
              onClick={() => void onDelete(row)}
              disabled={isSaving}
              className="ml-auto text-[11px] text-red-400 hover:text-red-300 disabled:opacity-50"
            >
              Delete
            </button>
          </div>

          <div className="text-[10px] text-gray-500 pt-1 border-t border-gray-700/50">
            {reconcileFailed ? (
              <span className="text-red-400">
                Last AWS sync failed: {row.last_reconcile_error}
              </span>
            ) : row.last_reconciled_at ? (
              <span>
                Last synced with AWS{' '}
                {parseServerDate(row.last_reconciled_at).toLocaleString()}
              </span>
            ) : (
              <span>Not yet synced to AWS.</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

// ── Schedules card ───────────────────────────────────────────────────────
// Owns ALL schedule-related state + API calls so unrelated parent re-renders
// (Manual Run inputs, jobs polling every 5 s) don't reconcile this section,
// AND interactions inside this card (typing the new-schedule name, editing a
// cron, toggling an enable switch) don't bubble up and reconcile the rest of
// the page. Memoized on the small set of stable props it needs from parent.
const SchedulesCard = memo(function SchedulesCard({
  userIsAdmin,
  sortedAdapters,
  adapterTiers,
}: {
  userIsAdmin: boolean;
  sortedAdapters: readonly string[];
  adapterTiers: Record<string, FetcherTier>;
}) {
  const [schedules, setSchedules] = useState<CrawlerSchedule[]>([]);
  const [schedulePresets, setSchedulePresets] = useState<
    Record<string, string>
  >({});
  const [scheduleDrafts, setScheduleDrafts] = useState<
    Record<string, ScheduleDraft>
  >({});
  const [isLoadingSchedules, setIsLoadingSchedules] = useState(false);
  const [isSchedulesUnavailable, setIsSchedulesUnavailable] = useState(false);
  const [savingScheduleId, setSavingScheduleId] = useState<string | null>(null);
  const [scheduleSaveError, setScheduleSaveError] = useState<string | null>(
    null
  );
  const [isReconcilingAll, setIsReconcilingAll] = useState(false);
  const [expandedScheduleIds, setExpandedScheduleIds] = useState<Set<string>>(
    () => new Set()
  );

  const fetchSchedules = useCallback(async () => {
    if (!userIsAdmin) return;
    setIsLoadingSchedules(true);
    try {
      const res = await adminApi.listCrawlerSchedules();
      setSchedules(res.data.items);
      setSchedulePresets(res.data.presets);
      setScheduleDrafts(
        Object.fromEntries(
          res.data.items.map((row) => {
            const preset = presetForExpression(
              row.schedule_expression,
              res.data.presets
            );
            return [
              row.id,
              {
                preset,
                customExpression:
                  preset === 'custom' ? row.schedule_expression : '',
              },
            ];
          })
        )
      );
      setIsSchedulesUnavailable(false);
    } catch {
      setIsSchedulesUnavailable(true);
    } finally {
      setIsLoadingSchedules(false);
    }
  }, [userIsAdmin]);

  // Read live presets through a ref so mergeScheduleRow stays referentially
  // stable for memoized children downstream.
  const schedulePresetsRef = useRef(schedulePresets);
  useEffect(() => {
    schedulePresetsRef.current = schedulePresets;
  }, [schedulePresets]);

  const mergeScheduleRow = useCallback((row: CrawlerSchedule) => {
    setSchedules((prev) => prev.map((r) => (r.id === row.id ? row : r)));
    setScheduleDrafts((prev) => {
      const preset = presetForExpression(
        row.schedule_expression,
        schedulePresetsRef.current
      );
      return {
        ...prev,
        [row.id]: {
          preset,
          customExpression: preset === 'custom' ? row.schedule_expression : '',
        },
      };
    });
  }, []);

  const handleSaveSchedule = useCallback(
    async (scheduleId: string, patch: CrawlerScheduleUpdate) => {
      setSavingScheduleId(scheduleId);
      setScheduleSaveError(null);
      try {
        const res = await adminApi.updateCrawlerSchedule(scheduleId, patch);
        mergeScheduleRow(res.data);
      } catch (e) {
        setScheduleSaveError(
          e instanceof Error ? e.message : 'Failed to update schedule.'
        );
      } finally {
        setSavingScheduleId(null);
      }
    },
    [mergeScheduleRow]
  );

  const handleToggleAdapterInSchedule = useCallback(
    async (row: CrawlerSchedule, adapterName: string) => {
      const current = row.adapters.map((a) => a.adapter_name);
      const next = current.includes(adapterName)
        ? current.filter((n) => n !== adapterName)
        : [...current, adapterName];
      await handleSaveSchedule(row.id, { adapters: next });
    },
    [handleSaveSchedule]
  );

  const handleCreateSchedule = useCallback(
    async (body: CrawlerScheduleCreate) => {
      setScheduleSaveError(null);
      await adminApi.createCrawlerSchedule(body);
      await fetchSchedules();
    },
    [fetchSchedules]
  );

  const handleDeleteSchedule = useCallback(async (row: CrawlerSchedule) => {
    if (
      !window.confirm(`Delete schedule '${row.name}'? This cannot be undone.`)
    )
      return;
    setSavingScheduleId(row.id);
    setScheduleSaveError(null);
    try {
      await adminApi.deleteCrawlerSchedule(row.id);
      setSchedules((prev) => prev.filter((r) => r.id !== row.id));
    } catch (e) {
      setScheduleSaveError(
        e instanceof Error ? e.message : 'Failed to delete schedule.'
      );
    } finally {
      setSavingScheduleId(null);
    }
  }, []);

  const handleReconcileAll = useCallback(async () => {
    setIsReconcilingAll(true);
    setScheduleSaveError(null);
    try {
      await adminApi.reconcileCrawlerSchedules();
      await fetchSchedules();
    } catch (e) {
      setScheduleSaveError(
        e instanceof Error ? e.message : 'Failed to sync schedules with AWS.'
      );
    } finally {
      setIsReconcilingAll(false);
    }
  }, [fetchSchedules]);

  const toggleScheduleExpanded = useCallback((id: string) => {
    setExpandedScheduleIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const setRowDraft = useCallback((id: string, draft: ScheduleDraft) => {
    setScheduleDrafts((prev) => ({ ...prev, [id]: draft }));
  }, []);

  useEffect(() => {
    void fetchSchedules();
  }, [fetchSchedules]);

  return (
    <Card padding="sm">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-white leading-tight">
            Crawler Schedules
          </h2>
          <p className="text-[11px] text-gray-400">
            Each schedule fires one EventBridge trigger and runs its members in
            parallel.
          </p>
        </div>
        <Button
          onClick={() => void handleReconcileAll()}
          disabled={
            isReconcilingAll || isLoadingSchedules || isSchedulesUnavailable
          }
          className="bg-gray-700 hover:bg-gray-600 text-white text-[11px] py-0.5 px-2 shrink-0"
        >
          {isReconcilingAll ? 'Syncing…' : 'Force sync with AWS'}
        </Button>
      </div>

      {isSchedulesUnavailable && (
        <div className="flex items-start gap-2 p-2 mb-2 rounded border border-yellow-600/50 bg-yellow-900/20 text-yellow-300 text-xs">
          <span className="mt-0.5 shrink-0">⚠</span>
          <span>
            Schedules unavailable — backend did not respond. Requires AWS
            EventBridge plumbing.
          </span>
        </div>
      )}

      {scheduleSaveError && (
        <div className="mb-2">
          <ErrorAlert message={scheduleSaveError} />
        </div>
      )}

      <NewScheduleForm
        sortedAdapters={sortedAdapters}
        adapterTiers={adapterTiers}
        onCreate={handleCreateSchedule}
      />

      {isLoadingSchedules && schedules.length === 0 ? (
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      ) : schedules.length === 0 ? (
        <p className="text-xs text-gray-500 py-2">
          No schedules yet — create one above.
        </p>
      ) : (
        <div className="space-y-2">
          {schedules.map((row) => {
            const draft = scheduleDrafts[row.id];
            const draftPreset =
              draft?.preset ??
              presetForExpression(row.schedule_expression, schedulePresets);
            const draftCustomExpression = draft?.customExpression ?? '';
            const originalPreset = presetForExpression(
              row.schedule_expression,
              schedulePresets
            );
            return (
              <ScheduleRow
                key={row.id}
                row={row}
                draftPreset={draftPreset}
                draftCustomExpression={draftCustomExpression}
                originalPreset={originalPreset}
                presetExpressions={schedulePresets}
                sortedAdapters={sortedAdapters}
                adapterTiers={adapterTiers}
                isExpanded={expandedScheduleIds.has(row.id)}
                isSaving={savingScheduleId === row.id}
                onToggleExpanded={toggleScheduleExpanded}
                onSetDraft={setRowDraft}
                onSave={handleSaveSchedule}
                onDelete={handleDeleteSchedule}
                onToggleAdapter={handleToggleAdapterInSchedule}
              />
            );
          })}
        </div>
      )}
    </Card>
  );
});

function CrawlerAdmin() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const navigate = useNavigate();

  // Crawler tools
  const [crawlerAdapters, setCrawlerAdapters] = useState<string[]>([]);
  const [adapterTiers, setAdapterTiers] = useState<Record<string, FetcherTier>>(
    {}
  );
  const [selectedCrawlers, setSelectedCrawlers] = useState<Set<string>>(
    () => new Set()
  );
  const [crawlerLimits, setCrawlerLimits] = useState<Record<string, string>>(
    {}
  );
  const [globalCrawlerLimit, setGlobalCrawlerLimit] = useState<string>('');
  // Bumped whenever an external write (preset button click) needs to push a
  // new value into the LocalTextInput. The text input ignores parent value
  // changes until this counter ticks — keeping typing snappy without losing
  // the click-to-set behaviour.
  const [globalLimitSyncKey, setGlobalLimitSyncKey] = useState(0);
  const [crawlerDefaultCategoryId, setCrawlerDefaultCategoryId] =
    useState<string>('');
  const [crawlerCategories, setCrawlerCategories] = useState<
    CategoryResponse[]
  >([]);
  const [isLoadingCrawlers, setIsLoadingCrawlers] = useState(false);
  const [isRunningCrawlers, setIsRunningCrawlers] = useState(false);
  const [crawlerResult, setCrawlerResult] = useState<CrawlerRunResponse | null>(
    null
  );
  const [crawlerError, setCrawlerError] = useState<string | null>(null);
  const [crawlerDelaySec, setCrawlerDelaySec] = useState<number>(5);
  const [crawlerHtmlSaveDir, setCrawlerHtmlSaveDir] = useState<string>('');
  const [skipKnownUrls, setSkipKnownUrls] = useState<boolean>(false);

  // Rescrape
  const [isRescrapingArchives, setIsRescrapingArchives] = useState(false);
  const [rescrapeArchivesResult, setRescrapeArchivesResult] =
    useState<RescrapeArchivesQueuedResponse | null>(null);
  const [rescrapeArchivesError, setRescrapeArchivesError] = useState<
    string | null
  >(null);

  // Background jobs
  const [jobsList, setJobsList] = useState<BackgroundJobList | null>(null);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  // Schedules state lives entirely inside SchedulesCard so unrelated parent
  // state churn (jobs poll, manual-run inputs) doesn't reconcile schedules,
  // and schedule-side interactions don't reconcile the rest of the page.

  // Per-adapter retailer tuning (separate from schedule membership).
  const [adapterConfigs, setAdapterConfigs] = useState<CrawlerAdapterConfig[]>(
    []
  );
  const [isLoadingConfigs, setIsLoadingConfigs] = useState(false);
  const [savingConfigName, setSavingConfigName] = useState<string | null>(null);
  const [configSaveError, setConfigSaveError] = useState<string | null>(null);

  // Per-adapter crawled_pages breakdown by parse_status (pending/parsed/gone/failed).
  // Drives the parsed/total progress pill so catalog size stays visible across
  // interrupted runs.
  const [adapterStatusCounts, setAdapterStatusCounts] = useState<
    Record<string, Record<string, number>>
  >({});

  // Stable handlers for the BackgroundJobsCard so its memo can skip on
  // unrelated parent re-renders.
  const handleToggleJobExpanded = useCallback((id: string) => {
    setExpandedJobId((prev) => (prev === id ? null : id));
  }, []);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  const fetchCrawlers = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingCrawlers(true);
    try {
      const [adaptersRes, categoriesRes, countsRes] = await Promise.all([
        adminApi.getCrawlers(),
        categoriesApi.getCategories(),
        adminApi
          .getCrawledPageCountsBySourceAndStatus()
          .catch(() => ({ data: {} })),
      ]);
      setCrawlerAdapters(adaptersRes.data.adapters);
      // Default to all selected on first load so the common workflow is
      // "set a global limit, uncheck anything to skip, Run selected."
      setSelectedCrawlers((prev) =>
        prev.size === 0 ? new Set(adaptersRes.data.adapters) : prev
      );
      const tiers: Record<string, FetcherTier> = {};
      for (const info of adaptersRes.data.adapter_info ?? []) {
        tiers[info.name] = UNVERIFIED_ADAPTERS.has(info.name)
          ? 'unverified'
          : info.tier;
      }
      setAdapterTiers(tiers);
      setCrawlerCategories(categoriesRes.data);
      setAdapterStatusCounts(countsRes.data);
      const otherCategory = categoriesRes.data.find(
        (c: CategoryResponse) => c.name.toLowerCase() === 'other'
      );
      if (otherCategory) {
        setCrawlerDefaultCategoryId(String(otherCategory.id));
      }
    } catch {
      setCrawlerAdapters([]);
      setCrawlerCategories([]);
    } finally {
      setIsLoadingCrawlers(false);
    }
  }, [user?.is_admin]);

  const fetchJobs = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingJobs(true);
    try {
      const res = await adminApi.listJobs({ limit: 20 });
      setJobsList(res.data);
    } catch {
      // silently fail
    } finally {
      setIsLoadingJobs(false);
    }
  }, [user?.is_admin]);

  const fetchAdapterConfigs = useCallback(async () => {
    if (!user?.is_admin) return;
    setIsLoadingConfigs(true);
    try {
      const res = await adminApi.listCrawlerAdapterConfigs();
      setAdapterConfigs(res.data.items);
    } catch {
      setAdapterConfigs([]);
    } finally {
      setIsLoadingConfigs(false);
    }
  }, [user?.is_admin]);

  const handleSaveAdapterConfig = useCallback(
    async (adapterName: string, patch: CrawlerAdapterConfigUpdate) => {
      setSavingConfigName(adapterName);
      setConfigSaveError(null);
      try {
        const res = await adminApi.updateCrawlerAdapterConfig(
          adapterName,
          patch
        );
        setAdapterConfigs((prev) =>
          prev.map((r) => (r.adapter_name === adapterName ? res.data : r))
        );
      } catch (e) {
        setConfigSaveError(
          e instanceof Error
            ? `${adapterName}: ${e.message}`
            : `${adapterName}: failed to update tuning.`
        );
      } finally {
        setSavingConfigName(null);
      }
    },
    []
  );

  useEffect(() => {
    void fetchCrawlers();
    void fetchJobs();
    void fetchAdapterConfigs();
  }, [fetchCrawlers, fetchJobs, fetchAdapterConfigs]);

  // Per-running-crawler-job live progress keyed by job id. Populated by the
  // 5 s poll below and consumed by the in-progress card.
  const [jobProgress, setJobProgress] = useState<
    Record<string, CrawlerJobProgress>
  >({});

  // Read jobsList through a ref inside the polling callback so the function
  // identity stays stable. If we put jobsList in the dep array, the 5 s poll
  // interval below would tear down and recreate every time jobs update —
  // which is every poll cycle, defeating the throttle.
  const jobsListRef = useRef(jobsList);
  useEffect(() => {
    jobsListRef.current = jobsList;
  }, [jobsList]);

  const fetchProgressForRunning = useCallback(async () => {
    const running = (jobsListRef.current?.items ?? []).filter(
      (j) => j.status === 'running' && j.job_type === 'crawler_run'
    );
    if (running.length === 0) {
      setJobProgress((prev) => (Object.keys(prev).length === 0 ? prev : {}));
      return;
    }
    const results = await Promise.all(
      running.map((j) =>
        adminApi
          .getCrawlerJobProgress(j.id)
          .then((r) => [j.id, r.data] as const)
          .catch(() => null)
      )
    );
    setJobProgress((prev) => {
      const next: Record<string, CrawlerJobProgress> = {};
      for (const entry of results) {
        if (entry) next[entry[0]] = entry[1];
      }
      // Bail on setState if nothing changed — keeps referential equality for
      // consumers memoized on jobProgress.
      const prevKeys = Object.keys(prev).sort();
      const nextKeys = Object.keys(next).sort();
      if (
        prevKeys.length === nextKeys.length &&
        prevKeys.every((k, i) => k === nextKeys[i]) &&
        prevKeys.every((k) => prev[k] === next[k])
      ) {
        return prev;
      }
      return next;
    });
  }, []);

  // Poll jobs every 5 s while any job is running. Keyed on the running-state
  // transition rather than jobsList so the interval isn't recreated on every
  // poll's setState.
  const hasRunningJob = !!jobsList?.items.some((j) => j.status === 'running');
  useEffect(() => {
    if (!hasRunningJob) return;
    // Fetch progress immediately on transition into running so the panel
    // doesn't look empty for up to 5 s.
    void fetchProgressForRunning();
    const id = setInterval(() => {
      void fetchJobs();
      void fetchProgressForRunning();
    }, 5000);
    return () => clearInterval(id);
  }, [hasRunningJob, fetchJobs, fetchProgressForRunning]);

  // Stable handler for the BackgroundJobsCard cancel button.
  const handleCancelJob = useCallback(
    (id: string) => {
      void adminApi
        .cancelJob(id)
        .then(() => fetchJobs())
        .catch(() => undefined);
    },
    [fetchJobs]
  );

  const toggleCrawlerSelection = useCallback((adapter: string) => {
    setSelectedCrawlers((prev) => {
      const next = new Set(prev);
      if (next.has(adapter)) {
        next.delete(adapter);
      } else {
        next.add(adapter);
      }
      return next;
    });
  }, []);

  // Stable per-adapter limit setter so memoized rows don't re-render when the
  // parent re-renders for unrelated reasons.
  const setCrawlerLimitForAdapter = useCallback(
    (adapter: string, value: string) => {
      setCrawlerLimits((prev) =>
        (prev[adapter] ?? '') === value ? prev : { ...prev, [adapter]: value }
      );
    },
    []
  );

  const selectAllCrawlers = () => {
    setSelectedCrawlers(new Set(crawlerAdapters));
  };

  const deselectAllCrawlers = () => {
    setSelectedCrawlers(new Set());
  };

  /**
   * Toggle every adapter of a given fetcher tier at once without disturbing
   * adapters from other tiers. If the tier is already fully selected, deselect
   * all of its members; otherwise select every member (covers the mixed/empty
   * case with a single click).
   */
  const toggleTierSelection = (tier: FetcherTier) => {
    const membersOfTier = crawlerAdapters.filter(
      (name) => adapterTiers[name] === tier
    );
    if (membersOfTier.length === 0) return;
    setSelectedCrawlers((prev) => {
      const next = new Set(prev);
      const allSelected = membersOfTier.every((name) => next.has(name));
      if (allSelected) {
        for (const name of membersOfTier) next.delete(name);
      } else {
        for (const name of membersOfTier) next.add(name);
      }
      return next;
    });
  };

  // Sorted adapter list — only recomputes when adapters or tier metadata
  // changes. Used by Live Crawlers, New Schedule chips, and any other
  // tier-grouped renderer. Sorting ~100 items per render is cheap on its
  // own but compounds with the rest of the page; memoizing also hands a
  // stable reference to memoized children.
  const sortedAdapters = useMemo(
    () => sortAdaptersByTier(crawlerAdapters, adapterTiers),
    [crawlerAdapters, adapterTiers]
  );
  const sortedAdapterConfigs = useMemo(
    () =>
      [...adapterConfigs].sort((a, b) => {
        const ta = adapterTiers[a.adapter_name];
        const tb = adapterTiers[b.adapter_name];
        const da = ta ? TIER_SORT_ORDER[ta] : 3;
        const db = tb ? TIER_SORT_ORDER[tb] : 3;
        if (da !== db) return da - db;
        return a.adapter_name.localeCompare(b.adapter_name);
      }),
    [adapterConfigs, adapterTiers]
  );

  // Tier toggle stats for the Live Crawlers selector. Recomputes only when
  // the adapter set, their tiers, or the selection actually change — not on
  // unrelated keystrokes (e.g. typing into the new-schedule name input).
  const tierToggleStats = useMemo(() => {
    return (['http', 'tls', 'browser', 'unverified'] as const)
      .map((tier) => {
        const members = crawlerAdapters.filter(
          (name) => adapterTiers[name] === tier
        );
        if (members.length === 0) return null;
        const selectedCount = members.reduce(
          (n, name) => (selectedCrawlers.has(name) ? n + 1 : n),
          0
        );
        return { tier, total: members.length, selectedCount };
      })
      .filter(
        (x): x is { tier: FetcherTier; total: number; selectedCount: number } =>
          x !== null
      );
  }, [crawlerAdapters, adapterTiers, selectedCrawlers]);

  const handleRunSelectedCrawlers = async () => {
    const adapters = Array.from(selectedCrawlers);
    if (adapters.length === 0) {
      setCrawlerError('Select at least one crawler.');
      return;
    }
    await runCrawlersWithAdapters(adapters);
  };

  const handleRunAllCrawlers = async () => {
    await runCrawlersWithAdapters(['all']);
  };

  const runCrawlersWithAdapters = async (adapters: string[]) => {
    if (!crawlerDefaultCategoryId) {
      setCrawlerError('Select a default category.');
      return;
    }

    setIsRunningCrawlers(true);
    setCrawlerError(null);
    setCrawlerResult(null);

    const limits: Record<string, number> = {};
    const globalLimitNum =
      globalCrawlerLimit.trim() === ''
        ? null
        : parseInt(globalCrawlerLimit, 10);
    const useGlobalLimit =
      globalLimitNum != null && !isNaN(globalLimitNum) && globalLimitNum > 0;

    if (adapters[0] !== 'all') {
      for (const adapter of adapters) {
        const val = crawlerLimits[adapter]?.trim();
        if (val) {
          const n = parseInt(val, 10);
          if (!isNaN(n) && n > 0) {
            limits[adapter] = n;
          }
        }
      }
    }

    try {
      const body: CrawlerRunRequest = {
        adapters,
        crawler_default_category_id: crawlerDefaultCategoryId,
        parallel: true,
        delay_sec: crawlerDelaySec,
      };
      if (Object.keys(limits).length > 0) body.limits = limits;
      if (useGlobalLimit && globalLimitNum != null && globalLimitNum > 0)
        body.global_limit = globalLimitNum;
      if (crawlerHtmlSaveDir.trim()) {
        body.crawl_html_save_dir = crawlerHtmlSaveDir.trim();
      }
      if (skipKnownUrls) body.skip_known_urls = true;
      const response = await adminApi.runCrawlers(body);
      setCrawlerResult(response.data);
      setCrawlerError(null);
      void fetchJobs();
    } catch (error) {
      setCrawlerError(
        error instanceof Error ? error.message : 'Failed to run crawlers.'
      );
    } finally {
      setIsRunningCrawlers(false);
    }
  };

  const handleRescrapeArchives = async () => {
    if (!crawlerDefaultCategoryId) {
      setRescrapeArchivesError('Select a default category.');
      return;
    }

    setIsRescrapingArchives(true);
    setRescrapeArchivesResult(null);
    setRescrapeArchivesError(null);
    try {
      const body: RescrapeArchivesRequest = {
        default_category_id: crawlerDefaultCategoryId,
      };
      const response = await adminApi.rescrapeArchives(body);
      setRescrapeArchivesResult(response.data);
      void fetchJobs();
    } catch (error) {
      setRescrapeArchivesError(
        error instanceof Error
          ? error.message
          : 'Failed to start rescrape archives job.'
      );
    } finally {
      setIsRescrapingArchives(false);
    }
  };

  if (isAuthLoading || !user) {
    return (
      <div className="container mx-auto px-3 py-4">
        <PageHeader title="Crawler & Jobs" />
        {isAuthLoading ? (
          <div className="flex justify-center items-center py-12">
            <Spinner size="lg" text="Loading…" />
          </div>
        ) : (
          <Card>
            <ErrorAlert message="Please log in to access the admin dashboard." />
          </Card>
        )}
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="container mx-auto px-3 py-4">
        <PageHeader title="Crawler & Jobs" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-3 py-4">
      <PageHeader
        title="Crawler & Jobs"
        subtitle="Run crawlers, manage archives, configure schedule, and monitor background jobs"
      />

      <div className="flex items-center justify-between gap-2 mb-2">
        <Button onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </Button>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="text-muted-foreground">Fetcher tiers:</span>
          {(['http', 'tls', 'browser'] as const).map((t) => (
            <span
              key={t}
              title={TIER_META[t].full}
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border ${TIER_META[t].badge}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${TIER_META[t].dot}`}
              />
              {TIER_META[t].label}{' '}
              <span className="text-muted-foreground/80">
                {t === 'http' ? 'plain' : t === 'tls' ? 'TLS' : 'browser'}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Two manual columns instead of CSS multi-column. CSS columns with
          form controls inside trigger expensive repaints/relayouts on scroll
          in Chromium; manual two-column distribution gives the same
          masonry-style visual without that cost. Card distribution pairs
          one short + one tall card per column to balance heights. */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 items-start">
        {/* Column 1: Schedules (small) + Adapter Tuning (tall) */}
        <div className="space-y-3 min-w-0">
          {/* Crawler Schedules */}
          <SchedulesCard
            userIsAdmin={!!user?.is_admin}
            sortedAdapters={sortedAdapters}
            adapterTiers={adapterTiers}
          />

          {/* Adapter Tuning */}
          <AdapterTuningCard
            isLoadingConfigs={isLoadingConfigs}
            adapterConfigs={adapterConfigs}
            sortedAdapterConfigs={sortedAdapterConfigs}
            adapterTiers={adapterTiers}
            savingConfigName={savingConfigName}
            adapterStatusCounts={adapterStatusCounts}
            crawlerCategories={crawlerCategories}
            configSaveError={configSaveError}
            onSave={handleSaveAdapterConfig}
          />
        </div>

        {/* Column 2: Background Jobs (small) + Manual Run (tall) */}
        <div className="space-y-3 min-w-0">
          {/* Background Jobs */}
          <BackgroundJobsCard
            jobsList={jobsList}
            isLoadingJobs={isLoadingJobs}
            expandedJobId={expandedJobId}
            jobProgress={jobProgress}
            adapterStatusCounts={adapterStatusCounts}
            onToggleExpanded={handleToggleJobExpanded}
            onCancel={handleCancelJob}
          />

          {/* Manual Run — one-off live crawl or archive rescrape */}
          <Card padding="sm">
            <h2 className="text-base font-semibold text-white leading-tight">
              Manual Run
            </h2>
            <p className="text-xs text-muted-foreground mb-2">
              Trigger a one-off live crawl or archive rescrape now, outside the
              scheduled cadence.
            </p>

            {isLoadingCrawlers ? (
              <div className="flex justify-center items-center py-6">
                <Spinner />
              </div>
            ) : (
              <>
                <div className="mb-2 p-2 rounded-lg border border-white/15 bg-gray-900/40">
                  <div className="grid grid-cols-1 gap-2">
                    <div>
                      <label className="block text-[10px] font-medium text-muted-foreground mb-0.5 uppercase tracking-wide">
                        Default category
                      </label>
                      <select
                        value={crawlerDefaultCategoryId}
                        onChange={(e) =>
                          setCrawlerDefaultCategoryId(e.target.value)
                        }
                        className="w-full px-2 py-1 text-xs rounded border border-white/20 bg-gray-800 text-foreground focus:border-success focus:ring-1 focus:ring-success/20 focus:outline-none"
                      >
                        <option value="">Select category...</option>
                        {crawlerCategories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div className="p-2 bg-success/10 border border-success/60 rounded-lg mb-2">
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-success">
                      Live crawlers
                    </h3>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="text-muted-foreground">
                        {selectedCrawlers.size}/{crawlerAdapters.length}{' '}
                        selected
                      </span>
                      <span className="text-muted-foreground">·</span>
                      <button
                        type="button"
                        onClick={selectAllCrawlers}
                        className="text-success hover:text-success/90"
                      >
                        All
                      </button>
                      <span className="text-muted-foreground">|</span>
                      <button
                        type="button"
                        onClick={deselectAllCrawlers}
                        className="text-success hover:text-success/90"
                      >
                        None
                      </button>
                      <span className="text-muted-foreground">·</span>
                      {tierToggleStats.map(({ tier, total, selectedCount }) => {
                        const allSelected = selectedCount === total;
                        const someSelected = selectedCount > 0 && !allSelected;
                        const meta = TIER_META[tier];
                        const cls = allSelected
                          ? meta.chipSelected
                          : someSelected
                            ? `${meta.chipUnselected} ring-1 ring-inset ring-current/40`
                            : meta.chipUnselected;
                        return (
                          <button
                            key={tier}
                            type="button"
                            onClick={() => toggleTierSelection(tier)}
                            title={`${meta.full} — ${selectedCount}/${total} selected (click to ${allSelected ? 'deselect' : 'select'} all)`}
                            className={`px-1.5 py-0.5 rounded border text-[10px] font-mono leading-none transition-colors ${cls}`}
                          >
                            {meta.label}
                            <span className="ml-1 opacity-70">
                              {selectedCount}/{total}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <p className="text-[10px] text-muted-foreground mb-2">
                    Tip: <span className="text-foreground">global limit</span>{' '}
                    applies per adapter (e.g. 50 = up to 50 pages each, not
                    shared). Uncheck any to skip, then click{' '}
                    <span className="text-foreground">Run selected</span>.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
                    <div>
                      <label className="block text-[10px] font-medium text-muted-foreground mb-0.5 uppercase">
                        Delay
                      </label>
                      <select
                        value={crawlerDelaySec}
                        onChange={(e) =>
                          setCrawlerDelaySec(Number(e.target.value))
                        }
                        className="w-full px-1.5 py-1 text-xs rounded border border-white/20 bg-gray-800 text-foreground focus:border-success focus:outline-none"
                      >
                        <option value={2.5}>2.5 s</option>
                        <option value={5}>5 s</option>
                        <option value={10}>10 s</option>
                        <option value={15}>15 s</option>
                        <option value={30}>30 s</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-muted-foreground mb-0.5 uppercase">
                        Global limit
                      </label>
                      <div className="flex items-center gap-1">
                        <LocalTextInput
                          type="number"
                          min="1"
                          placeholder="—"
                          initialValue={globalCrawlerLimit}
                          inputKey={globalLimitSyncKey}
                          onCommit={setGlobalCrawlerLimit}
                          className={`${inputVariants()} min-h-0 py-1 text-xs w-full`}
                        />
                        {[25, 50, 100, 250].map((n) => {
                          const active = globalCrawlerLimit === String(n);
                          return (
                            <button
                              key={n}
                              type="button"
                              onClick={() => {
                                setGlobalCrawlerLimit(active ? '' : String(n));
                                setGlobalLimitSyncKey((k) => k + 1);
                              }}
                              className={`px-1.5 py-0.5 rounded border text-[10px] font-mono leading-none ${
                                active
                                  ? 'border-success bg-success/40 text-success'
                                  : 'border-gray-600 text-muted-foreground hover:border-success hover:text-success'
                              }`}
                              title={`Set global limit to ${n}`}
                            >
                              {n}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <label className="block text-[10px] font-medium text-muted-foreground mb-0.5 uppercase">
                        HTML save dir
                      </label>
                      <LocalTextInput
                        type="text"
                        placeholder="Optional"
                        initialValue={crawlerHtmlSaveDir}
                        onCommit={setCrawlerHtmlSaveDir}
                        className={`${inputVariants()} min-h-0 py-1 text-xs w-full`}
                      />
                    </div>
                  </div>
                  <label
                    htmlFor="skip-known-urls"
                    className="flex items-center gap-2 mb-2 text-xs text-foreground select-none cursor-pointer"
                  >
                    <input
                      id="skip-known-urls"
                      type="checkbox"
                      checked={skipKnownUrls}
                      onChange={(e) => setSkipKnownUrls(e.target.checked)}
                      className="h-3.5 w-3.5 rounded border-border bg-card text-success focus:ring-success"
                    />
                    Skip already-archived URLs
                    <span className="text-[10px] text-muted-foreground">
                      (omit parse_status=parsed)
                    </span>
                  </label>

                  <LiveCrawlerRowList
                    sortedAdapters={sortedAdapters}
                    adapterTiers={adapterTiers}
                    selectedCrawlers={selectedCrawlers}
                    crawlerLimits={crawlerLimits}
                    adapterStatusCounts={adapterStatusCounts}
                    onToggleSelected={toggleCrawlerSelection}
                    onLimitChange={setCrawlerLimitForAdapter}
                  />

                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() => void handleRunSelectedCrawlers()}
                      disabled={
                        isRunningCrawlers || selectedCrawlers.size === 0
                      }
                      className="bg-success hover:bg-success/90 text-white text-xs py-1 px-2.5"
                    >
                      {isRunningCrawlers ? (
                        <span className="flex items-center">
                          <Spinner size="sm" inline />
                          <span className="ml-1">Running...</span>
                        </span>
                      ) : (
                        `Run selected (${selectedCrawlers.size})`
                      )}
                    </Button>
                    <Button
                      onClick={() => void handleRunAllCrawlers()}
                      disabled={isRunningCrawlers}
                      className="bg-success hover:bg-success/90 text-white text-xs py-1 px-2.5"
                    >
                      Run all
                    </Button>
                  </div>

                  {crawlerError && (
                    <div className="mt-2">
                      <ErrorAlert message={crawlerError} />
                    </div>
                  )}

                  {crawlerResult && (
                    <div className="mt-2 p-1.5 rounded border border-success bg-gray-900/50 text-xs">
                      <div className="font-semibold text-success">
                        {crawlerResult.status === 'started'
                          ? 'Crawler job started'
                          : 'Crawler'}
                      </div>
                      <p className="text-foreground">{crawlerResult.message}</p>
                      {crawlerResult.adapters.length > 0 && (
                        <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                          {crawlerResult.adapters.join(', ')}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="p-2 bg-violet-900/10 border border-violet-700/60 rounded-lg">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-violet-200 mb-1">
                    Archive rescrape
                  </h3>
                  <p className="text-[11px] text-muted-foreground mb-2">
                    Re-run parse → ingest on every URL with archived HTML (same
                    pipeline as a live crawl). Background job — watch server
                    logs for per-outcome counts.
                  </p>
                  <Button
                    onClick={() => void handleRescrapeArchives()}
                    disabled={isRescrapingArchives}
                    className="bg-violet-600 hover:bg-violet-700 text-white text-xs py-1 px-2.5"
                  >
                    {isRescrapingArchives ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <Spinner size="sm" inline />
                        </span>
                        Starting…
                      </span>
                    ) : (
                      'Rescrape latest archives'
                    )}
                  </Button>
                  {rescrapeArchivesError && (
                    <div className="mt-2">
                      <ErrorAlert message={rescrapeArchivesError} />
                    </div>
                  )}
                  {rescrapeArchivesResult && (
                    <div className="mt-2 p-1.5 rounded border border-green-700 bg-green-900/20 text-xs">
                      <p className="font-semibold text-green-400">
                        {rescrapeArchivesResult.status === 'started'
                          ? 'Job queued.'
                          : rescrapeArchivesResult.status}
                      </p>
                      <p className="text-foreground text-[11px] mt-0.5">
                        {rescrapeArchivesResult.message}
                      </p>
                    </div>
                  )}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

export default CrawlerAdmin;
