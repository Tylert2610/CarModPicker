/**
 * Car generation lookup and search, the vehicle taxonomy build lists hang from.
 */

import { apiClient } from './client';
import type { CarGenerationRead } from '../types/Api';

/** Car generation lookup, search, and make or model browsing. */
export const carGenerationsApi = {
  getCar: (carId: string) =>
    apiClient.get<CarGenerationRead>(`/car-generations/${carId}`),
  listCars: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<CarGenerationRead[]>('/car-generations/', { params }),
  searchCars: (q: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarGenerationRead[]>('/car-generations/search', {
      params: { q, ...params },
    }),
  getCarsByMake: (make: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarGenerationRead[]>(
      `/car-generations/car-makes/${encodeURIComponent(make)}`,
      {
        params,
      }
    ),
  getCarsByMakeModel: (
    make: string,
    model: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<CarGenerationRead[]>(
      `/car-generations/car-makes/${encodeURIComponent(make)}/car-models/${encodeURIComponent(model)}`,
      { params }
    ),
  getCarsByIds: (ids: string[]) =>
    apiClient.get<CarGenerationRead[]>('/car-generations/by-ids', {
      params: { ids },
    }),
  getCarMakeStats: () =>
    apiClient.get<Record<string, number>>('/car-generations/stats/car-makes'),
  countCars: () => apiClient.get<{ count: number }>('/car-generations/count'),
  countMakes: () =>
    apiClient.get<{ count: number }>('/car-generations/car-makes/count'),
  countCarModels: () =>
    apiClient.get<{ count: number }>('/car-generations/car-models/count'),
};
