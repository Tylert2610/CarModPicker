/**
 * Unauthenticated service endpoints used for health checks and smoke tests.
 */

import { apiClient } from './client';

/** Unauthenticated root and health endpoints. */
export const utilityApi = {
  getRoot: () => apiClient.get<Record<string, string>>('/'),
  healthCheck: () => apiClient.get<Record<string, unknown>>('/health'),
};
