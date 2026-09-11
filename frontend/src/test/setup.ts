/**
 * Global vitest setup. Registers jest-dom matchers and stubs the api client so a
 * test that forgets to mock it cannot reach the network.
 */

import '@testing-library/jest-dom';
import { ApiError } from '@webbpulse/api-client';
import { vi, beforeAll, afterAll } from 'vitest';

const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null }),
  post: vi.fn().mockResolvedValue({ data: null }),
  put: vi.fn().mockResolvedValue({ data: null }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: null }),
};

vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: vi.fn(),
  isApiErrorWithStatus: (error: unknown): error is ApiError =>
    error instanceof ApiError,
}));

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
