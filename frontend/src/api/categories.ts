// Categories domain API. Mirrors backend endpoints/categories.py.
// Read-only; categories are seeded from backend part_categories_data.
import { apiClient } from './client';
import type { CategoryResponse, PartRead } from '../types/Api';

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

  // Count endpoints
  getCategoryPartsCount: (categoryId: string) =>
    apiClient.get<{ count: number }>(`/categories/${categoryId}/parts-count`),
  countCategories: () => apiClient.get<{ count: number }>('/categories/count'),
};
