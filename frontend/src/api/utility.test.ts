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
    expect(result.data['status']).toBe('healthy');
  });
});
