import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListPhasesApi } from './build_list_phases';

const mockPhaseId = 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa';

describe('buildListPhasesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('updatePhase PUTs body to /build-list-phases/:phaseId', async () => {
    const body = { name: 'Renamed Phase', sort_order: 2 };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        id: mockPhaseId,
        build_list_id: '33333333-3333-7333-8333-333333333333',
        name: body.name,
        sort_order: body.sort_order,
      },
    });

    const result = await buildListPhasesApi.updatePhase(mockPhaseId, body);

    expect(apiClient.put).toHaveBeenCalledWith(
      `/build-list-phases/${mockPhaseId}`,
      body
    );
    expect(result.data.id).toBe(mockPhaseId);
  });

  it('deletePhase DELETEs /build-list-phases/:phaseId', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: {
        id: mockPhaseId,
        build_list_id: '33333333-3333-7333-8333-333333333333',
        name: 'Deleted',
        sort_order: 0,
      },
    });

    const result = await buildListPhasesApi.deletePhase(mockPhaseId);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/build-list-phases/${mockPhaseId}`
    );
    expect(result.data.id).toBe(mockPhaseId);
  });
});
