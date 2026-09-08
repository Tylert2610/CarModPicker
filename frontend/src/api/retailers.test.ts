// Phase 8 Wave 1 API-module test pattern (PATTERNS.md §7).
// `vi.mocked(apiClient.method)` and `expect(apiClient.method).toHaveBeenCalledWith(...)`
// both reference methods as unbound values; the eslint rule `@typescript-eslint/unbound-method`
// is a false positive here because vitest's mock runtime invokes them via the same
// `mockApiClient` object identity (see frontend/src/test/setup.ts dual-mock block).
// D-15 decision: retailersApi is a single-method GET wrapper (currently only
// `countRetailers`). Plan 08-03 evaluated Option B (vitest coverage.exclude) vs
// Option A (minimal smoke test). Chose Option A because:
//   1. Executable content is ~1 line but trivially mockable under the existing
//      dual-mock infrastructure — test cost is 10 lines.
//   2. Writing the test contributes 100% coverage for src/api/retailers.ts at
//      zero marginal infrastructure cost.
//   3. When the retailers surface grows (planner: "richer surface lands when
//      needed"), a future plan has an existing file to extend instead of
//      removing a coverage.exclude entry + authoring from scratch.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { retailersApi } from './retailers';

describe('retailersApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('countRetailers GETs /retailers/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 5 } });

    const result = await retailersApi.countRetailers();

    expect(apiClient.get).toHaveBeenCalledWith('/retailers/count');
    expect(result.data).toEqual({ count: 5 });
  });
});
