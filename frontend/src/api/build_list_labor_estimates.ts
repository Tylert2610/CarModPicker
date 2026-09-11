import { apiClient } from './client';
import type {
  BuildListLaborEstimateRead,
  BuildListLaborEstimateUpdate,
} from '../types/Api';

export const buildListLaborEstimatesApi = {
  updateLaborEstimate: (
    laborEstimateId: string,
    data: BuildListLaborEstimateUpdate
  ) =>
    apiClient.put<BuildListLaborEstimateRead>(
      `/build-list-labor-estimates/${laborEstimateId}`,
      data
    ),
  deleteLaborEstimate: (laborEstimateId: string) =>
    apiClient.delete<BuildListLaborEstimateRead>(
      `/build-list-labor-estimates/${laborEstimateId}`
    ),
};
