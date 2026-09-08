// Retailers domain API. Mirrors backend endpoints/retailers.py.
// Currently only exposes a count endpoint; richer surface lands when needed.
import { apiClient } from './client';

export const retailersApi = {
  countRetailers: () => apiClient.get<{ count: number }>('/retailers/count'),
};
