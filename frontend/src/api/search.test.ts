// Tests for searchApi (frontend/src/api/search.ts).
// Plan 08-06 (Wave 1, Utility cluster).
//
// Canonical scaffold: PATTERNS.md §7. apiClient is auto-mocked by
// frontend/src/test/setup.ts (D-18), so no per-file vi.mock is required.
//
// Narrow the mocked HTTP-verb references at module scope via a cast to
// `MockedFunction<typeof apiClient.<verb>>`. setup.ts installs a vi.fn()
// for every verb, so this cast is accurate. Accessing each verb once here
// avoids tripping two strict-lint rules at every call site:
//   - @typescript-eslint/unbound-method (method reference of a class)
//   - @typescript-eslint/no-unsafe-call (vi.mocked(apiClient) returns an
//     `error`-typed object for AxiosInstance)
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import { searchApi, type SearchResults } from './search';
import { mockBuildList, mockPart, mockUser } from '../test/mocks/api';

// setup.ts (D-18) installs `vi.fn()` for every HTTP verb; the cast below
// reflects the mocked reality. The original AxiosInstance method IS unbound
// in general, but here apiClient IS the mock object, so the cast is safe.

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

function makeEmptyResults(query: string): SearchResults {
  return {
    build_lists: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    users: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    parts: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    query,
  };
}

describe('searchApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('search forwards query params to /search/ via GET', async () => {
    const payload: SearchResults = {
      build_lists: {
        data: [mockBuildList],
        total: 1,
        has_next: false,
        skip: 0,
        limit: 10,
      },
      users: {
        data: [mockUser],
        total: 1,
        has_next: false,
        skip: 0,
        limit: 10,
      },
      parts: {
        data: [mockPart],
        total: 1,
        has_next: false,
        skip: 0,
        limit: 10,
      },
      query: 'honda civic',
    };
    getMock.mockResolvedValueOnce({ data: payload });

    const result = await searchApi.search({
      q: 'honda civic',
      skip: 0,
      limit: 10,
    });

    expect(getMock).toHaveBeenCalledWith('/search/', {
      params: { q: 'honda civic', skip: 0, limit: 10 },
    });
    expect(result.data).toEqual(payload);
    expect(result.data.query).toBe('honda civic');
  });

  it('search passes through the q-only form without skip/limit', async () => {
    getMock.mockResolvedValueOnce({
      data: makeEmptyResults('civic'),
    });

    await searchApi.search({ q: 'civic' });

    expect(getMock).toHaveBeenCalledWith('/search/', {
      params: { q: 'civic' },
    });
    expect(getMock).toHaveBeenCalledTimes(1);
  });

  it('search returns the empty-results envelope verbatim for a no-match query', async () => {
    const payload = makeEmptyResults('xyzzy-no-match');
    getMock.mockResolvedValueOnce({ data: payload });

    const result = await searchApi.search({ q: 'xyzzy-no-match' });

    expect(result.data.build_lists.data).toHaveLength(0);
    expect(result.data.users.data).toHaveLength(0);
    expect(result.data.parts.data).toHaveLength(0);
    expect(result.data.query).toBe('xyzzy-no-match');
  });
});
