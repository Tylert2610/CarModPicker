import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildResponse } from '../test/apiResponse';
import { apiClient } from '../api/client';
import { usePartPriceSummaries } from './usePartPriceSummaries';
import type {
  PriceHistoryBatchResponse,
  PriceHistorySummary,
} from '../types/Api';

function makeSummary(
  overrides: Partial<PriceHistorySummary> = {}
): PriceHistorySummary {
  return {
    min_cents: 1000,
    max_cents: 2000,
    last_cents: 1500,
    last_observed_at: '2026-04-01T00:00:00Z',
    trend: 'flat',
    observation_count: 3,
    ...overrides,
  };
}

function buildBatch(
  summaries: Record<string, PriceHistorySummary>,
  window = '90d'
): PriceHistoryBatchResponse {
  return {
    summaries,
    window,
    requested_count: Object.keys(summaries).length,
    found_count: Object.keys(summaries).length,
  };
}

describe('usePartPriceSummaries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('short-circuits when partIds is empty (no fetch fired)', async () => {
    const { result } = renderHook(() => usePartPriceSummaries([]));
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.summaries).toEqual({});
    expect(result.current.error).toBeNull();
    expect(vi.mocked(apiClient.post)).not.toHaveBeenCalled();
  });

  it('fetches batch summary for non-empty ids and exposes summaries map', async () => {
    const summaries = {
      'p-1': makeSummary({ trend: 'up' }),
      'p-2': makeSummary({ trend: 'down' }),
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce(
      buildResponse(buildBatch(summaries))
    );

    const { result } = renderHook(() => usePartPriceSummaries(['p-1', 'p-2']));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.summaries).toEqual(summaries);
    expect(result.current.error).toBeNull();
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/parts/price-history',
      expect.objectContaining({
        part_ids: ['p-1', 'p-2'],
        window: '90d',
      })
    );
  });

  it('uses the provided window argument', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce(
      buildResponse(buildBatch({}, '30d'))
    );

    renderHook(() => usePartPriceSummaries(['x'], '30d'));

    await waitFor(() => {
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
    });
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
      '/parts/price-history',
      expect.objectContaining({ part_ids: ['x'], window: '30d' })
    );
  });

  it('debounces identical re-renders into a single fetch (stable key)', async () => {
    vi.mocked(apiClient.post).mockResolvedValue(
      buildResponse(buildBatch({ a: makeSummary() }))
    );

    const { rerender } = renderHook(
      ({ ids }: { ids: string[] }) => usePartPriceSummaries(ids),
      { initialProps: { ids: ['a', 'b'] } }
    );

    await waitFor(() => {
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
    });

    rerender({ ids: ['a', 'b'] });
    rerender({ ids: ['b', 'a'] });
    await act(async () => {
      await Promise.resolve();
    });
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);
  });

  it('logs and returns error state on failure without throwing', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.mocked(apiClient.post).mockRejectedValueOnce(new Error('network down'));

    const { result } = renderHook(() => usePartPriceSummaries(['p-1']));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe('network down');
    expect(result.current.summaries).toEqual({});
    expect(warn).toHaveBeenCalledWith(
      '[usePartPriceSummaries]',
      expect.any(Error)
    );
    warn.mockRestore();
  });

  it('refetches when partIds change to a different stable key', async () => {
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce(buildResponse(buildBatch({ a: makeSummary() })))
      .mockResolvedValueOnce(buildResponse(buildBatch({ c: makeSummary() })));

    const { rerender, result } = renderHook(
      ({ ids }: { ids: string[] }) => usePartPriceSummaries(ids),
      { initialProps: { ids: ['a'] } }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(1);

    rerender({ ids: ['c'] });

    await waitFor(() => {
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledTimes(2);
    });
  });
});
