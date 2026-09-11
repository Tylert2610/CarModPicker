import { partsApi } from '../../api/parts';
import type { PartPriceHistoryReadWithRetailer } from '../../types/Api';

interface CacheEntry {
  history: PartPriceHistoryReadWithRetailer[];
  cachedAt: number;
}

const CACHE_TTL_MS = 5 * 60 * 1000;
const historyCache = new Map<string, CacheEntry>();

const inflight = new Map<string, Promise<PartPriceHistoryReadWithRetailer[]>>();

/** Returns a part's cached price history, or null when absent or stale. */
export function getCachedHistory(
  partId: string
): PartPriceHistoryReadWithRetailer[] | null {
  const entry = historyCache.get(partId);
  if (!entry) return null;
  if (Date.now() - entry.cachedAt > CACHE_TTL_MS) {
    historyCache.delete(partId);
    return null;
  }
  return entry.history;
}

/**
 * Fetches a part's 90 day price history and caches it, sharing one request
 * per part id so a table of sparklines does not refetch the same part.
 */
export function fetchHistory(
  partId: string
): Promise<PartPriceHistoryReadWithRetailer[]> {
  const existing = inflight.get(partId);
  if (existing) return existing;

  const p = partsApi
    .getPartPriceHistorySummary(partId, { window: '90d' })
    .then((res) => {
      const history = res.data?.history ?? [];
      historyCache.set(partId, { history, cachedAt: Date.now() });
      inflight.delete(partId);
      return history;
    })
    .catch((err: unknown) => {
      inflight.delete(partId);
      console.warn('[SparklineCell]', partId, err);
      return [];
    });

  inflight.set(partId, p);
  return p;
}

/** Clears the cache and in-flight map. For tests. */
export function __resetSparklineCellCache(): void {
  historyCache.clear();
  inflight.clear();
}
