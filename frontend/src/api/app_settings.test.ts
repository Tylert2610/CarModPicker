/**
 * Tests for appSettingsApi.
 */

import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import {
  appSettingsApi,
  type AppSettings,
  type AppSettingsUpdate,
} from './app_settings';

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

const putMock = apiClient.put as MockedFunction<typeof apiClient.put>;

const baseSettings: AppSettings = {
  premium_disabled: false,
  updated_at: '2026-04-24T00:00:00Z',
};

describe('appSettingsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('get hits /app-settings/ with GET and returns the envelope', async () => {
    getMock.mockResolvedValueOnce({ data: baseSettings });

    const result = await appSettingsApi.get();

    expect(getMock).toHaveBeenCalledWith('/app-settings/');
    expect(getMock).toHaveBeenCalledTimes(1);
    expect(result.data).toEqual(baseSettings);
    expect(result.data.premium_disabled).toBe(false);
  });

  it('update PUTs the body to /app-settings/ and returns the updated envelope', async () => {
    const body: AppSettingsUpdate = { premium_disabled: true };
    const updated: AppSettings = {
      premium_disabled: true,
      updated_at: '2026-04-24T00:05:00Z',
    };
    putMock.mockResolvedValueOnce({ data: updated });

    const result = await appSettingsApi.update(body);

    expect(putMock).toHaveBeenCalledWith('/app-settings/', body);
    expect(putMock).toHaveBeenCalledTimes(1);
    expect(result.data.premium_disabled).toBe(true);
    expect(result.data.updated_at).toBe('2026-04-24T00:05:00Z');
  });

  it('update forwards an empty patch body unchanged', async () => {
    const body: AppSettingsUpdate = {};
    putMock.mockResolvedValueOnce({ data: baseSettings });

    await appSettingsApi.update(body);

    expect(putMock).toHaveBeenCalledWith('/app-settings/', {});
  });
});
