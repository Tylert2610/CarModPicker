// Parts domain API. Mirrors backend endpoints/parts.py.
// Global shared parts in the catalog. Part-scoped vote/report wrappers
// (legacy) live in `votes.ts` / `reports.ts`.
import { apiClient } from './client';
import type {
  PaginatedResponse,
  PartCreate,
  PartListingReadWithRetailer,
  PartRead,
  PartReadWithVotes,
  PartUpdate,
  PriceHistoryBatchRequest,
  PriceHistoryBatchResponse,
  PriceHistorySinglePartResponse,
} from '../types/Api';

export const partsApi = {
  // Get all global parts with filtering
  getParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    car_id?: string;
    search?: string;
  }) => apiClient.get<PartRead[]>('/parts/', { params }),

  // Get global parts with vote data
  getPartsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    category_ids?: string[];
    car_id?: string;
    car_ids?: string[];
    part_manufacturer_id?: string;
    part_manufacturer_ids?: string[];
    user_id?: string;
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    universal?: boolean;
  }) =>
    apiClient.get<PaginatedResponse<PartReadWithVotes>>('/parts/with-votes', {
      params,
    }),

  // Get available filter options given current filters (for cascading filters)
  getFilterOptions: (params?: {
    category_ids?: string[];
    part_manufacturer_ids?: string[];
    car_id?: string;
    car_ids?: string[];
    search?: string;
    user_id?: string;
    universal?: boolean;
  }) =>
    apiClient.get<{
      category_ids: string[];
      part_manufacturer_ids: string[];
      car_ids?: string[];
      make_names?: string[];
    }>('/parts/filter-options', { params }),

  // Filter by category
  getPartsByCategory: (
    categoryId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(`/parts/category/${categoryId}`, {
      params: { filter_id: categoryId, ...params },
    }),

  // Create a new global part
  createPart: (data: PartCreate) => apiClient.post<PartRead>('/parts/', data),

  // Get specific global part
  getPart: (partId: string) => apiClient.get<PartRead>(`/parts/${partId}`),

  // Get retailer listings for a part (price by retailer)
  getPartListings: (partId: string) =>
    apiClient.get<PartListingReadWithRetailer[]>(`/parts/${partId}/listings`),

  // Get aggregated price history (summary + per-retailer breakdown + listings)
  // for a single part. New object-shape endpoint introduced in M002/S05.
  getPartPriceHistorySummary: (
    partId: string,
    params?: {
      window?: PriceHistoryBatchRequest['window'];
      retailer_id?: string;
    }
  ) =>
    apiClient.get<PriceHistorySinglePartResponse>(
      `/parts/${partId}/price-history`,
      { params }
    ),

  // Batch price-history summary for up to 100 part IDs in a single round trip.
  getBatchPriceHistorySummary: (body: PriceHistoryBatchRequest) =>
    apiClient.post<PriceHistoryBatchResponse>('/parts/price-history', body),

  // Update global part
  updatePart: (partId: string, data: PartUpdate) =>
    apiClient.put<PartRead>(`/parts/${partId}`, data),

  // Delete global part
  deletePart: (partId: string) =>
    apiClient.delete<PartRead>(`/parts/${partId}`),

  // Image management (requires edit permission)
  appendPartImages: (partId: string, fileKeys: string[]) =>
    apiClient.post<PartRead>(`/parts/${partId}/append-images`, {
      file_keys: fileKeys,
    }),
  removePartImage: (partId: string, imageIndex: number) =>
    apiClient.delete<PartRead>(`/parts/${partId}/images/${imageIndex}`),
  setPartPrimaryImage: (partId: string, index: number) =>
    apiClient.patch<PartRead>(`/parts/${partId}/primary-image`, {
      index,
    }),

  // Count endpoints
  countParts: () => apiClient.get<{ count: number }>('/parts/count'),
  countPartsByUser: (userId: string) =>
    apiClient.get<{ count: number }>(`/parts/user/${userId}/count`),

  // Check if product URL exists
  checkProductUrl: (productUrl: string) =>
    apiClient.get<{ existing_part_id: string | null }>('/parts/check-url', {
      params: { product_url: productUrl },
    }),
};
