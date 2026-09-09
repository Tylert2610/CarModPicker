// Build List Phases domain API. Mirrors backend endpoints/build_list_phases.py.
// Update/delete by phase ID; create lives on buildListsApi (parent-scoped).
import { apiClient } from './client';
import type { BuildListPhaseRead, BuildListPhaseUpdate } from '../types/Api';

export const buildListPhasesApi = {
  updatePhase: (phaseId: string, data: BuildListPhaseUpdate) =>
    apiClient.put<BuildListPhaseRead>(`/build-list-phases/${phaseId}`, data),
  deletePhase: (phaseId: string) =>
    apiClient.delete<BuildListPhaseRead>(`/build-list-phases/${phaseId}`),
};
