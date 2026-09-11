import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  adminApi,
  type ExtractionHealthResponse,
  type FailureRateRow,
} from '../../api/admin';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import Spinner from '../../components/ui/spinner';
import { useAuth } from '../../hooks/useAuth';

type TierKey = 'http' | 'tls' | 'browser';
const TIER_ORDER: readonly TierKey[] = ['http', 'tls', 'browser'] as const;

interface AxiosLikeError {
  response?: { status?: number };
  message?: string;
}

function formatErrorMessage(err: unknown): string {
  const e = err as AxiosLikeError;
  const status = e.response?.status;
  const detail = e.message ?? 'Request failed';
  const prefix = status ? `HTTP ${status}` : 'Network error';
  return `${prefix} — ${detail}. Check crawled_pages.parse_status for ingest health.`;
}

function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

/**
 * Admin view of extraction health, reporting adapter compliance and per tier
 * field coverage.
 */
function ExtractionHealth() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [data, setData] = useState<ExtractionHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [reloadTick, setReloadTick] = useState<number>(0);

  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  useEffect(() => {
    if (!user || !user.is_admin) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    adminApi
      .getExtractionHealth()
      .then((response) => {
        if (cancelled) return;
        setData(response.data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(formatErrorMessage(err));
        setData(null);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, reloadTick]);

  const sortedFailureRows: FailureRateRow[] = useMemo(() => {
    if (!data) return [];
    return [...data.failure_rate_7d].sort((a, b) => b.rate - a.rate);
  }, [data]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Extraction Health" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Extraction Health" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  const subtitle = data
    ? `Last ${String(data.window.days)} days (since ${data.window.since})`
    : 'Adapter compliance, per-tier coverage, and 7d failure rates';

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Extraction Health" subtitle={subtitle} />

      {error && (
        <div className="mb-4">
          <ErrorAlert message={error} />
        </div>
      )}

      {loading && !data && (
        <Card>
          <Spinner text="Loading extraction health…" />
        </Card>
      )}

      {data && (
        <>
          {/* Compliance */}
          <Card>
            <div className="flex items-start justify-between gap-4 mb-4">
              <SectionHeader title="Adapter Compliance" />
              <Button
                variant="secondary"
                onClick={() => setReloadTick((n) => n + 1)}
                disabled={loading}
                aria-label="Refresh extraction health"
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </Button>
            </div>

            <div className="flex flex-col items-start gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-4xl font-bold text-white">
                  {data.compliance.compliant} / {data.compliance.total}
                </div>
                <p className="text-sm text-gray-400 mt-1">
                  Adapters meeting the universal-field contract
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {TIER_ORDER.map((tier) => (
                  <span
                    key={tier}
                    data-testid={`compliance-pill-${tier}`}
                    className="inline-flex items-center rounded-full border border-gray-700 bg-gray-800 px-3 py-1 text-sm font-medium text-gray-200"
                  >
                    <span className="uppercase tracking-wide text-xs text-gray-400 mr-2">
                      {tier}
                    </span>
                    <span className="font-mono">
                      {data.compliance.per_tier[tier]}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          </Card>

          {/* Coverage heatmap */}
          <div className="mt-6">
            <Card>
              <SectionHeader title="Per-Tier Field Coverage" />
              <div className="space-y-6">
                {Object.entries(data.coverage.per_tier ?? {}).map(
                  ([tier, block]) => {
                    const partsTotal = block.parts_total;
                    const summary =
                      partsTotal === 0
                        ? '—'
                        : `${block.parts_with_specs} / ${partsTotal}`;
                    const fieldNames = Object.keys(block.per_field).sort();
                    return (
                      <div
                        key={tier}
                        data-testid={`coverage-tier-${tier}`}
                        className="border border-gray-700 rounded-lg p-4"
                      >
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-200 uppercase tracking-wide">
                            {tier}
                          </h3>
                          <span className="text-sm text-gray-300 font-mono">
                            {summary}
                          </span>
                        </div>
                        {fieldNames.length === 0 ? (
                          <p className="text-sm text-gray-500">
                            No field-presence data for this tier.
                          </p>
                        ) : (
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-xs uppercase text-gray-500">
                                <th className="py-1 pr-4 font-medium">Field</th>
                                <th className="py-1 font-medium">Presence</th>
                              </tr>
                            </thead>
                            <tbody>
                              {fieldNames.map((field) => {
                                const ratio = block.per_field[field] ?? 0;
                                return (
                                  <tr
                                    key={field}
                                    className="border-t border-gray-800"
                                  >
                                    <td className="py-1 pr-4 font-mono text-gray-300">
                                      {field}
                                    </td>
                                    <td className="py-1 text-gray-200">
                                      {partsTotal === 0
                                        ? '—'
                                        : formatPercent(ratio)}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        )}
                      </div>
                    );
                  }
                )}
              </div>
            </Card>
          </div>

          {/* Failure-rate table */}
          <div className="mt-6">
            <Card>
              <SectionHeader title="7-Day Per-Adapter Failure Rate" />
              {sortedFailureRows.length === 0 ? (
                <p className="text-sm text-gray-400">No failures in window</p>
              ) : (
                <div className="overflow-x-auto">
                  <table
                    className="w-full text-sm"
                    data-testid="failure-rate-table"
                  >
                    <thead>
                      <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-700">
                        <th className="py-2 pr-4 font-medium">Adapter</th>
                        <th className="py-2 pr-4 font-medium">Tier</th>
                        <th className="py-2 pr-4 font-medium">Parsed</th>
                        <th className="py-2 pr-4 font-medium">Failed</th>
                        <th className="py-2 font-medium">Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedFailureRows.map((row) => (
                        <tr
                          key={row.adapter}
                          className="border-b border-gray-800"
                        >
                          <td className="py-2 pr-4 font-mono text-gray-200">
                            {row.adapter}
                          </td>
                          <td className="py-2 pr-4 uppercase text-gray-400">
                            {row.tier}
                          </td>
                          <td className="py-2 pr-4 text-gray-300">
                            {row.parsed}
                          </td>
                          <td className="py-2 pr-4 text-gray-300">
                            {row.failed}
                          </td>
                          <td className="py-2 text-gray-100 font-mono">
                            {formatPercent(row.rate)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

export default ExtractionHealth;
