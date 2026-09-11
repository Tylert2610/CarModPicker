/**
 * Phases that group a build list's parts. Phases are created through the build
 * list endpoints, so only update and delete live here.
 */

import { apiClient } from './client';
import type { BuildListPhaseRead, BuildListPhaseUpdate } from '../types/Api';

/** Update and delete for build list phases. */
export const buildListPhasesApi = {
  updatePhase: (phaseId: string, data: BuildListPhaseUpdate) =>
    apiClient.put<BuildListPhaseRead>(`/build-list-phases/${phaseId}`, data),
  deletePhase: (phaseId: string) =>
    apiClient.delete<BuildListPhaseRead>(`/build-list-phases/${phaseId}`),
};
