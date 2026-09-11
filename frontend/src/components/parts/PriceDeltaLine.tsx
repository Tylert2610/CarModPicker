import type { PriceHistorySummary } from '../../types/Api';

interface PriceDeltaLineProps {
  summary: PriceHistorySummary | null | undefined;
}

const TREND_ARROW: Record<PriceHistorySummary['trend'], string> = {
  up: '↑',
  down: '↓',
  flat: '·',
};

/** Cents as a whole-dollar amount. */
function formatDollars(cents: number): string {
  return `$${Math.round(cents / 100).toLocaleString()}`;
}

/** An ISO timestamp as a local date, falling back to the raw value. */
function formatLocalDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** A one-line summary of how a part's price has moved over the window. */
export default function PriceDeltaLine({ summary }: PriceDeltaLineProps) {
  if (!summary) return null;
  if (summary.observation_count === 0) return null;

  const arrow = TREND_ARROW[summary.trend];

  if (summary.observation_count === 1) {
    const since =
      summary.last_observed_at !== null
        ? formatLocalDate(summary.last_observed_at)
        : 'recently';
    return (
      <span data-testid="price-delta-line" className="text-xs text-gray-400">
        <span data-testid="price-delta-arrow" aria-hidden="true">
          {arrow}
        </span>{' '}
        Tracked since {since}
      </span>
    );
  }

  const minStr =
    summary.min_cents !== null ? formatDollars(summary.min_cents) : '—';
  const maxStr =
    summary.max_cents !== null ? formatDollars(summary.max_cents) : '—';

  return (
    <span data-testid="price-delta-line" className="text-xs text-gray-400">
      <span data-testid="price-delta-arrow" aria-hidden="true">
        {arrow}
      </span>{' '}
      {minStr} → {maxStr}
    </span>
  );
}
