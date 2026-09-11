import { useMemo } from 'react';
import type { PartPriceHistoryReadWithRetailer } from '../../types/Api';

interface SparklineProps {
  history: PartPriceHistoryReadWithRetailer[];
  width?: number;
  height?: number;
  ariaLabel?: string;
}

const DEFAULT_WIDTH = 80;
const DEFAULT_HEIGHT = 24;
const STROKE_WIDTH = 1.5;

/** A compact inline SVG trend line for a series of numbers. */
export default function Sparkline({
  history,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  ariaLabel = 'Price history sparkline',
}: SparklineProps) {
  const sorted = useMemo(
    () =>
      [...history].sort(
        (a, b) =>
          new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
      ),
    [history]
  );

  if (sorted.length === 0) return null;

  if (sorted.length === 1) {
    const cx = width / 2;
    const cy = height / 2;
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={ariaLabel}
        data-testid="sparkline"
      >
        <circle
          cx={cx}
          cy={cy}
          r={2}
          fill="hsl(var(--primary))"
          data-testid="sparkline-dot"
        />
      </svg>
    );
  }

  const prices = sorted.map((p) => p.price_cents);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const range = maxPrice - minPrice;

  const xStep = sorted.length > 1 ? width / (sorted.length - 1) : 0;
  const points = sorted
    .map((p, i) => {
      const x = i * xStep;
      const y =
        range === 0
          ? height / 2
          : height - ((p.price_cents - minPrice) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={ariaLabel}
      data-testid="sparkline"
    >
      <polyline
        points={points}
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth={STROKE_WIDTH}
        strokeLinecap="round"
        strokeLinejoin="round"
        data-testid="sparkline-polyline"
      />
    </svg>
  );
}
