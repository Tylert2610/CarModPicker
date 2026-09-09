// Tests for utilityApi (frontend/src/api/utility.ts).
// Plan 08-06 (Wave 1, Utility cluster) — Option A (test) chosen over D-15
// exclude because each method hits a distinct hard-coded URL (`/` vs
// `/health`), which IS the behavior worth asserting. Testing also preserves
// 9 lines of coverage that an exclusion would drop.
//
// Canonical scaffold: PATTERNS.md §7. apiClient is auto-mocked by
// frontend/src/test/setup.ts (D-18), so no per-file vi.mock is required.
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import { utilityApi } from './utility';

// setup.ts (D-18) installs `vi.fn()` for every HTTP verb; the cast below
// reflects the mocked reality. apiClient IS the mock object here, so the
// cast is safe.

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

describe('utilityApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getRoot hits the root path "/" via GET', async () => {
    const payload: Record<string, string> = {
      message: 'CarModPicker API',
      status: 'ok',
    };
    getMock.mockResolvedValueOnce({ data: payload });

    const result = await utilityApi.getRoot();

    expect(getMock).toHaveBeenCalledWith('/');
    expect(getMock).toHaveBeenCalledTimes(1);
    expect(result.data).toEqual(payload);
  });

  it('healthCheck hits "/health" via GET and returns the liveness envelope', async () => {
    const payload: Record<string, unknown> = {
      status: 'healthy',
      timestamp: '2026-04-24T00:00:00Z',
      version: '1.0.0',
    };
    getMock.mockResolvedValueOnce({ data: payload });

    const result = await utilityApi.healthCheck();

    expect(getMock).toHaveBeenCalledWith('/health');
    expect(getMock).toHaveBeenCalledTimes(1);
    // `data` is typed `Record<string, unknown>`, so TS4111 requires bracket
    // notation for the index-signature lookup.
    expect(result.data['status']).toBe('healthy');
  });
});
