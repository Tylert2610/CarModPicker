import { apiClient } from './client';
import type {
  BuildListCreate,
  BuildListLaborEstimateCreate,
  BuildListLaborEstimateRead,
  BuildListPhaseCreate,
  BuildListPhaseRead,
  BuildListRead,
  BuildListReadWithVotes,
  BuildListUpdate,
  PaginatedResponse,
} from '../types/Api';

export const buildListsApi = {
  createBuildList: (data: BuildListCreate) =>
    apiClient.post<BuildListRead>('/build-lists/', data),
  getBuildList: (buildListId: string) =>
    apiClient.get<BuildListRead>(`/build-lists/${buildListId}`),
  updateBuildList: (buildListId: string, data: BuildListUpdate) =>
    apiClient.put<BuildListRead>(`/build-lists/${buildListId}`, data),
  deleteBuildList: (buildListId: string) =>
    apiClient.delete<BuildListRead>(`/build-lists/${buildListId}`),

  listBuildLists: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }) => apiClient.get<BuildListRead[]>('/build-lists/', { params }),
  getBuildListsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    car_id?: string;
    car_ids?: string[];
    owner_id?: string;
    min_cost_cents?: number;
    max_cost_cents?: number;
    sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
  }) =>
    apiClient.get<PaginatedResponse<BuildListReadWithVotes>>(
      '/build-lists/with-votes',
      {
        params,
      }
    ),
  getBuildListsByCar: (
    carId: string,
    params?: { skip?: number; limit?: number; search?: string }
  ) =>
    apiClient.get<PaginatedResponse<BuildListRead>>(
      `/build-lists/car/${carId}`,
      { params }
    ),
  getBuildListsByUser: (
    userId: string,
    params?: { skip?: number; limit?: number }
  ) =>
    apiClient.get<BuildListRead[]>(`/build-lists/user/${userId}`, { params }),

  countBuildLists: () => apiClient.get<{ count: number }>('/build-lists/count'),

  copyBuildList: (buildListId: string, newName?: string) =>
    apiClient.post<BuildListRead>(`/build-lists/${buildListId}/copy`, {
      new_name: newName || null,
    }),

  getPhases: (buildListId: string) =>
    apiClient.get<BuildListPhaseRead[]>(`/build-lists/${buildListId}/phases`),
  createPhase: (buildListId: string, data: BuildListPhaseCreate) =>
    apiClient.post<BuildListPhaseRead>(
      `/build-lists/${buildListId}/phases`,
      data
    ),

  getLaborEstimates: (buildListId: string) =>
    apiClient.get<BuildListLaborEstimateRead[]>(
      `/build-lists/${buildListId}/labor-estimates`
    ),
  createLaborEstimate: (
    buildListId: string,
    data: BuildListLaborEstimateCreate
  ) =>
    apiClient.post<BuildListLaborEstimateRead>(
      `/build-lists/${buildListId}/labor-estimates`,
      data
    ),

  appendBuildListImages: (buildListId: string, fileKeys: string[]) =>
    apiClient.post<BuildListRead>(`/build-lists/${buildListId}/append-images`, {
      file_keys: fileKeys,
    }),
  removeBuildListImage: (buildListId: string, imageIndex: number) =>
    apiClient.delete<BuildListRead>(
      `/build-lists/${buildListId}/images/${imageIndex}`
    ),
  setBuildListPrimaryImage: (buildListId: string, index: number) =>
    apiClient.patch<BuildListRead>(
      `/build-lists/${buildListId}/primary-image`,
      { index }
    ),
};
