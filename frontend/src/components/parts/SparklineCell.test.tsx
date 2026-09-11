import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { buildResponse } from '../../test/apiResponse';
import { apiClient } from '../../api/client';
import SparklineCell from './SparklineCell';
import { __resetSparklineCellCache } from './sparkline-cache';
import type {
  PartPriceHistoryReadWithRetailer,
  PriceHistorySinglePartResponse,
  PriceHistorySummary,
} from '../../types/Api';

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

function makeHistory(count: number): PartPriceHistoryReadWithRetailer[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `h-${i}`,
    part_listing_id: 'pl-1',
    price_cents: 1000 + i * 100,
    observed_at: `2026-03-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
    retailer_id: 'r1',
    retailer_name: 'AmazingMart',
  }));
}

function makeSingleResponse(
  history: PartPriceHistoryReadWithRetailer[]
): PriceHistorySinglePartResponse {
  return {
    summary: makeSummary({ observation_count: history.length }),
    retailers: [],
    history,
    window: '90d',
  };
}

type IOEntryPartial = Pick<IntersectionObserverEntry, 'isIntersecting'>;
interface IOMock {
  observe: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  unobserve: ReturnType<typeof vi.fn>;
  trigger: (entries: IOEntryPartial[]) => void;
}
const ioInstances: IOMock[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  __resetSparklineCellCache();
  ioInstances.length = 0;

  type IOCb = (entries: IOEntryPartial[]) => void;
  class FakeIntersectionObserver {
    constructor(cb: IOCb) {
      const inst: IOMock = {
        observe: vi.fn(),
        disconnect: vi.fn(),
        unobserve: vi.fn(),
        trigger: (entries) => cb(entries),
      };
      ioInstances.push(inst);
      Object.assign(this, inst);
    }
  }
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SparklineCell', () => {
  it('renders nothing when summary is null', () => {
    const { container } = render(<SparklineCell partId="p-1" summary={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when observation_count is 0', () => {
    const { container } = render(
      <SparklineCell
        partId="p-1"
        summary={makeSummary({ observation_count: 0 })}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders a centered dot for a single observation without fetching', () => {
    const { container } = render(
      <SparklineCell
        partId="p-1"
        summary={makeSummary({
          observation_count: 1,
          last_cents: 1500,
          last_observed_at: '2026-04-01T00:00:00Z',
        })}
      />
    );
    const dot = container.querySelector('[data-testid="sparkline-dot"]');
    expect(dot).not.toBeNull();
    expect(vi.mocked(apiClient.get)).not.toHaveBeenCalled();
  });

  it('does not fetch until IntersectionObserver fires (lazy-load)', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(
      buildResponse(makeSingleResponse(makeHistory(3)))
    );

    const { container } = render(
      <SparklineCell
        partId="p-1"
        summary={makeSummary({ observation_count: 3 })}
      />
    );

    expect(
      container.querySelector('[data-testid="sparkline-cell"]')
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="sparkline-polyline"]')
    ).toBeNull();
    expect(vi.mocked(apiClient.get)).not.toHaveBeenCalled();

    expect(ioInstances).toHaveLength(1);
    await act(async () => {
      ioInstances[0]!.trigger([{ isIntersecting: true }]);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(
        container.querySelector('[data-testid="sparkline-polyline"]')
      ).not.toBeNull();
    });
  });

  it('caches per-partId across mounts within TTL — second mount does not refetch', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(
      buildResponse(makeSingleResponse(makeHistory(3)))
    );

    const first = render(
      <SparklineCell
        partId="p-1"
        summary={makeSummary({ observation_count: 3 })}
      />
    );
    await act(async () => {
      ioInstances[0]!.trigger([{ isIntersecting: true }]);
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledTimes(1);
    });
    first.unmount();

    const second = render(
      <SparklineCell
        partId="p-1"
        summary={makeSummary({ observation_count: 3 })}
      />
    );

    await waitFor(() => {
      expect(
        second.container.querySelector('[data-testid="sparkline-polyline"]')
      ).not.toBeNull();
    });
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledTimes(1);
  });

  it('survives a fetch failure (no throw, no svg path)', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('boom'));

    const { container } = render(
      <SparklineCell
        partId="p-err"
        summary={makeSummary({ observation_count: 3 })}
      />
    );
    await act(async () => {
      ioInstances[0]!.trigger([{ isIntersecting: true }]);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(warn).toHaveBeenCalled();
    });
    expect(
      container.querySelector('[data-testid="sparkline-polyline"]')
    ).toBeNull();

    warn.mockRestore();
  });
});
