// Build List Parts domain API. Mirrors backend endpoints/build_list_parts.py.
// Relationships between global parts and build lists.
import { apiClient } from './client';
import type {
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartReadWithPart,
  BuildListPartUpdate,
  PartCreate,
} from '../types/Api';

export const buildListPartsApi = {
  // Create a new global part and add it to a build list as a build list part
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
  // Add an existing global part to a build list as a build list part
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
  // Update a build list part (notes, etc.) by build list and global part IDs
  updateBuildListPart: (
    buildListId: string,
    partId: string,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`,
      data
    ),
  // Update a build list part by its own ID
  updateBuildListPartById: (
    buildListPartId: string,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/${buildListPartId}`,
      data
    ),
  // Remove a build list part from a build list (doesn't delete the global part)
  removeBuildListPart: (buildListId: string, partId: string) =>
    apiClient.delete<BuildListPartRead>(
      `/build-list-parts/${buildListId}/parts/${partId}`
    ),
  // Delete a build list part by its own ID
  deleteBuildListPartById: (buildListPartId: string) =>
    apiClient.delete<BuildListPartRead>(`/build-list-parts/${buildListPartId}`),
  // Get all build list parts in a build list (basic info)
  getBuildListPartsBasic: (buildListId: string) =>
    apiClient.get<BuildListPartRead[]>(`/build-list-parts/${buildListId}`),
  // Get all build list parts in a build list (with global part details)
  getBuildListParts: (buildListId: string) =>
    apiClient.get<BuildListPartReadWithPart[]>(
      `/build-list-parts/${buildListId}/parts`
    ),
  // Count build lists containing a specific global part
  countBuildListsContainingPart: (partId: string) =>
    apiClient.get<{ count: number }>(
      `/build-list-parts/parts/${partId}/build-lists/count`
    ),
  // Count all build list parts
  countBuildListParts: () =>
    apiClient.get<{ count: number }>('/build-list-parts/count'),
};
