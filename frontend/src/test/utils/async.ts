import { act } from '@testing-library/react';
import { vi } from 'vitest';

/**
 * Fake-timer helpers for the admin polling tests, which drive `setInterval`
 * only.
 */

/**
 * Enters fake-timer mode, pairing with `stopFakeTimers()`. Fakes only timers
 * and `Date`, leaving microtasks real so async `waitFor` still settles.
 */
export function startFakeTimers(): void {
  vi.useFakeTimers({ toFake: ['setInterval', 'setTimeout', 'Date'] });
}

export function stopFakeTimers(): void {
  vi.useRealTimers();
}

/**
 * Advances timers and flushes React state inside one `act` batch, so promise
 * chains started by a polling callback settle before assertions run. Await it
 * rather than calling `vi.advanceTimersByTime`, which leaves stale DOM.
 */
export async function advanceTimersAndFlush(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
