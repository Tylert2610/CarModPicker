/**
 * Labor estimate rows on a build list. Estimates are created through the phase
 * endpoints, so only update and delete live here.
 */

import { apiClient } from './client';
import type {
  BuildListLaborEstimateRead,
  BuildListLaborEstimateUpdate,
} from '../types/Api';

/** Update and delete for build list labor estimates. */
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
