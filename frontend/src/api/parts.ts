/**
 * Parts catalog: lookup, search, filtering, and the price summaries shown on a part.
 */

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

/** Part lookup, search, filtering, and price history. */
export const partsApi = {
  getParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    car_id?: string;
    search?: string;
  }) => apiClient.get<PartRead[]>('/parts/', { params }),

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

  getPartsByCategory: (
    categoryId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(`/parts/category/${categoryId}`, {
      params: { filter_id: categoryId, ...params },
    }),

  createPart: (data: PartCreate) => apiClient.post<PartRead>('/parts/', data),

  getPart: (partId: string) => apiClient.get<PartRead>(`/parts/${partId}`),

  getPartListings: (partId: string) =>
    apiClient.get<PartListingReadWithRetailer[]>(`/parts/${partId}/listings`),

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

  getBatchPriceHistorySummary: (body: PriceHistoryBatchRequest) =>
    apiClient.post<PriceHistoryBatchResponse>('/parts/price-history', body),

  updatePart: (partId: string, data: PartUpdate) =>
    apiClient.put<PartRead>(`/parts/${partId}`, data),

  deletePart: (partId: string) =>
    apiClient.delete<PartRead>(`/parts/${partId}`),

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

  countParts: () => apiClient.get<{ count: number }>('/parts/count'),
  countPartsByUser: (userId: string) =>
    apiClient.get<{ count: number }>(`/parts/user/${userId}/count`),

  checkProductUrl: (productUrl: string) =>
    apiClient.get<{ existing_part_id: string | null }>('/parts/check-url', {
      params: { product_url: productUrl },
    }),
};
