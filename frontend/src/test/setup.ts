import '@testing-library/jest-dom';
import { ApiError } from '@webbpulse/api-client';
import { vi, beforeAll, afterAll } from 'vitest';

// Mock the API client to prevent network requests during tests
const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null }),
  post: vi.fn().mockResolvedValue({ data: null }),
  put: vi.fn().mockResolvedValue({ data: null }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: null }),
};

// Every domain module under `../api/<domain>` imports the shared transport
// from `../api/client`, so mocking that one module gives the whole API surface
// a single mocked client and keeps the real domain objects (authApi,
// buildListsApi, and the rest) intact.
//
// `isApiErrorWithStatus` is the real predicate rather than a stub. It performs
// no I/O, and a test that rejects with an `ApiError` expects the consumer's
// error branch to recognise it; stubbing it would make every such branch
// silently take the "no status" path.
vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: vi.fn(),
  isApiErrorWithStatus: (error: unknown): error is ApiError =>
    error instanceof ApiError,
}));

// Mock console methods to reduce noise in tests
const originalError = console.error;
const originalWarn = console.warn;

beforeAll(() => {
  console.error = (...args: unknown[]) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render is no longer supported')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };

  console.warn = (...args: unknown[]) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: componentWillReceiveProps') ||
        args[0].includes('Warning: componentWillUpdate'))
    ) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});
