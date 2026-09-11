import { useEffect, useRef, useState } from 'react';
import type {
  PartPriceHistoryReadWithRetailer,
  PriceHistorySummary,
} from '../../types/Api';
import Sparkline from '../charts/Sparkline';
import { fetchHistory, getCachedHistory } from './sparkline-cache';

interface SparklineCellProps {
  partId: string;
  summary: PriceHistorySummary | null | undefined;
  width?: number;
  height?: number;
  ariaLabel?: string;
}

const DEFAULT_WIDTH = 60;
const DEFAULT_HEIGHT = 16;

/** A table cell showing a part's price trend, fetched through the shared cache. */
export default function SparklineCell({
  partId,
  summary,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  ariaLabel,
}: SparklineCellProps) {
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const [history, setHistory] = useState<
    PartPriceHistoryReadWithRetailer[] | null
  >(() => getCachedHistory(partId));
  const [shouldFetch, setShouldFetch] = useState(false);

  const observationCount = summary?.observation_count ?? 0;
  const hasMulti = observationCount >= 2;

  useEffect(() => {
    if (!hasMulti) return;
    if (history !== null) return;

    const node = wrapperRef.current;
    if (!node) return;

    if (typeof IntersectionObserver === 'undefined') {
      setShouldFetch(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShouldFetch(true);
            observer.disconnect();
            observerRef.current = null;
            break;
          }
        }
      },
      { rootMargin: '100px' }
    );
    observer.observe(node);
    observerRef.current = observer;

    return () => {
      observer.disconnect();
      observerRef.current = null;
    };
  }, [partId, hasMulti, history]);

  useEffect(() => {
    if (!shouldFetch) return;
    if (history !== null) return;
    let cancelled = false;
    void fetchHistory(partId).then((h) => {
      if (cancelled) return;
      setHistory(h);
    });
    return () => {
      cancelled = true;
    };
  }, [shouldFetch, partId, history]);

  if (observationCount === 0 || !summary) {
    return null;
  }

  if (observationCount === 1) {
    const synthetic: PartPriceHistoryReadWithRetailer[] =
      summary.last_cents !== null && summary.last_observed_at !== null
        ? [
            {
              id: `synthetic-${partId}`,
              part_listing_id: `synthetic-${partId}`,
              price_cents: summary.last_cents,
              observed_at: summary.last_observed_at,
              retailer_id: 'synthetic',
              retailer_name: 'synthetic',
            },
          ]
        : [];
    return (
      <span ref={wrapperRef} data-testid="sparkline-cell" data-part-id={partId}>
        <Sparkline
          history={synthetic}
          width={width}
          height={height}
          ariaLabel={ariaLabel ?? 'Price history sparkline'}
        />
      </span>
    );
  }

  return (
    <span
      ref={wrapperRef}
      data-testid="sparkline-cell"
      data-part-id={partId}
      style={{ display: 'inline-block', width, height }}
    >
      {history && history.length > 0 ? (
        <Sparkline
          history={history}
          width={width}
          height={height}
          ariaLabel={ariaLabel ?? 'Price history sparkline'}
        />
      ) : null}
    </span>
  );
}
