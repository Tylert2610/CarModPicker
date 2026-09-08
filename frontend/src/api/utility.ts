// Utility / health API. No backend domain mirror — these are top-level
// liveness / root probes.
import { apiClient } from './client';

export const utilityApi = {
  getRoot: () => apiClient.get<Record<string, string>>('/'),
  healthCheck: () => apiClient.get<Record<string, unknown>>('/health'),
};
