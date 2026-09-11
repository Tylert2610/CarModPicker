/**
 * Part category lookup and the parts listed under each category.
 */

import { apiClient } from './client';
import type { CategoryResponse, PartRead } from '../types/Api';

/** Part category lookup and the parts under each category. */
export const categoriesApi = {
  getCategories: () => apiClient.get<CategoryResponse[]>('/categories/'),
  getCategory: (categoryId: string) =>
    apiClient.get<CategoryResponse>(`/categories/${categoryId}`),
  getPartsByCategory: (
    categoryId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(`/categories/${categoryId}/parts`, {
      params,
    }),

  getCategoryPartsCount: (categoryId: string) =>
    apiClient.get<{ count: number }>(`/categories/${categoryId}/parts-count`),
  countCategories: () => apiClient.get<{ count: number }>('/categories/count'),
};
