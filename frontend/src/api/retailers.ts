/**
 * Retailer lookup and the per-retailer listings that back part pricing.
 */

import { apiClient } from './client';

/** Retailer lookup and their part listings. */
export const retailersApi = {
  countRetailers: () => apiClient.get<{ count: number }>('/retailers/count'),
};
