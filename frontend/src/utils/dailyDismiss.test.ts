/**
 * Tests for dailyDismiss.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { dismissForToday, isDismissedToday } from './dailyDismiss';

const KEY = 'cmp_promo_dismissed_test';
const OTHER_KEY = 'cmp_other_promo_dismissed_test';

describe('dailyDismiss', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('reports not dismissed when nothing has been stored', () => {
    expect(isDismissedToday(KEY)).toBe(false);
  });

  it('stores the local calendar date, zero-padded, under the given key', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 4, 7, 13, 30));

    dismissForToday(KEY);

    expect(localStorage.getItem(KEY)).toBe('2026-05-07');
    expect(isDismissedToday(KEY)).toBe(true);
  });

  it('expires the dismissal once the local date rolls over', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 4, 7, 23, 59));
    dismissForToday(KEY);
    expect(isDismissedToday(KEY)).toBe(true);

    vi.setSystemTime(new Date(2026, 4, 8, 0, 1));
    expect(isDismissedToday(KEY)).toBe(false);
  });

  it('keeps dismissals for different keys independent', () => {
    dismissForToday(KEY);

    expect(isDismissedToday(KEY)).toBe(true);
    expect(isDismissedToday(OTHER_KEY)).toBe(false);
  });

  it('treats a stale stored date as not dismissed', () => {
    localStorage.setItem(KEY, '2020-01-01');

    expect(isDismissedToday(KEY)).toBe(false);
  });

  it('reports not dismissed when localStorage reads throw', () => {
    dismissForToday(KEY);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });

    expect(isDismissedToday(KEY)).toBe(false);
  });

  it('swallows localStorage write failures', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => dismissForToday(KEY)).not.toThrow();
  });
});
