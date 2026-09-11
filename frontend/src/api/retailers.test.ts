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
