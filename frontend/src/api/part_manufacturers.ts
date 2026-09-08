// Part Manufacturers domain API. Mirrors backend endpoints/part_manufacturers.py.
import { apiClient } from './client';
import type {
  PartManufacturerCreate,
  PartManufacturerResponse,
  PartManufacturerUpdate,
  PartRead,
} from '../types/Api';

export const partManufacturersApi = {
  getPartManufacturers: (activeOnly: boolean = true) =>
    apiClient.get<PartManufacturerResponse[]>('/part-manufacturers/', {
      params: { active_only: activeOnly },
    }),
  searchPartManufacturers: (
    q: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartManufacturerResponse[]>('/part-manufacturers/search', {
      params: { q, ...params },
    }),
  getPartManufacturer: (part_manufacturerId: string) =>
    apiClient.get<PartManufacturerResponse>(
      `/part-manufacturers/${part_manufacturerId}`
    ),
  createPartManufacturer: (data: PartManufacturerCreate) =>
    apiClient.post<PartManufacturerResponse>('/part-manufacturers/', data),
  updatePartManufacturer: (
    part_manufacturerId: string,
    data: PartManufacturerUpdate
  ) =>
    apiClient.put<PartManufacturerResponse>(
      `/part-manufacturers/${part_manufacturerId}`,
      data
    ),
  deletePartManufacturer: (part_manufacturerId: string) =>
    apiClient.delete<Record<string, string>>(
      `/part-manufacturers/${part_manufacturerId}`
    ),
  getPartsByPartManufacturer: (
    part_manufacturerId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<PartRead[]>(
      `/part-manufacturers/${part_manufacturerId}/parts`,
      {
        params,
      }
    ),
  getPartManufacturerPartsCount: (part_manufacturerId: string) =>
    apiClient.get<{ parts_count: number }>(
      `/part-manufacturers/${part_manufacturerId}/parts-count`
    ),
  countPartManufacturers: () =>
    apiClient.get<{ count: number }>('/part-manufacturers/count'),
  countPartManufacturersBySource: () =>
    apiClient.get<{ total: number }>('/part-manufacturers/counts/by-source'),
};
