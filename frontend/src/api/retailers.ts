import { apiClient } from './client';

export const retailersApi = {
  countRetailers: () => apiClient.get<{ count: number }>('/retailers/count'),
};
