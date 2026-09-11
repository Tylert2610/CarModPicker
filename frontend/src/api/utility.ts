import { apiClient } from './client';

export const utilityApi = {
  getRoot: () => apiClient.get<Record<string, string>>('/'),
  healthCheck: () => apiClient.get<Record<string, unknown>>('/health'),
};
