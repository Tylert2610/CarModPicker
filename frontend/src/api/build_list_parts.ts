import { apiClient } from './client';
import type {
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartReadWithPart,
  BuildListPartUpdate,
  PartCreate,
} from '../types/Api';

export const buildListPartsApi = {
  createPartAndAddToBuildList: (
    buildListId: string,
    partData: PartCreate,
    buildListPartData: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartReadWithPart>(
      `/build-list-parts/${buildListId}/create-and-add-part`,
      {
        name: partData.name,
        description: partData.description,
        image_urls: partData.image_urls,
        category_id: partData.category_id,
        car_ids: partData.car_ids ?? undefined,
        is_universal: partData.is_universal ?? false,
        part_manufacturer_id: partData.part_manufacturer_id,
        part_number: partData.part_number,
        retailer_id: partData.retailer_id,
        price_cents: partData.price_cents,
        product_url: partData.product_url,
        quantity: buildListPartData.quantity ?? 1,
        notes: buildListPartData.notes,
        build_list_phase_id: buildListPartData.build_list_phase_id ?? undefined,
      }
    ),
  addPartToBuildList: (
    buildListId: string,
    partId: string,
    data: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`,
      {
        ...data,
        build_list_phase_id: data.build_list_phase_id ?? undefined,
      }
    ),
  updateBuildListPart: (
    buildListId: string,
    partId: string,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`,
      data
    ),
  updateBuildListPartById: (
    buildListPartId: string,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListPartId}`,
      data
    ),
  removeBuildListPart: (buildListId: string, partId: string) =>
    apiClient.delete<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`
    ),
  deleteBuildListPartById: (buildListPartId: string) =>
    apiClient.delete<BuildListPartRead>(`/build-list-parts/${buildListPartId}`),
  getBuildListPartsBasic: (buildListId: string) =>
    apiClient.get<BuildListPartRead[]>(`/build-list-parts/${buildListId}`),
  getBuildListParts: (buildListId: string) =>
    apiClient.get<BuildListPartReadWithPart[]>(
      `/build-list-parts/${buildListId}/parts`
    ),
  countBuildListsContainingPart: (partId: string) =>
    apiClient.get<{ count: number }>(
      `/build-list-parts/parts/${partId}/build-lists/count`
    ),
  countBuildListParts: () =>
    apiClient.get<{ count: number }>('/build-list-parts/count'),
};
