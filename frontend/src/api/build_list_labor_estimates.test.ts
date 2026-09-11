import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListLaborEstimatesApi } from './build_list_labor_estimates';

const mockId = 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa';
const mockBuildListId = '33333333-3333-7333-8333-333333333333';

describe('buildListLaborEstimatesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('updateLaborEstimate PUTs body to /build-list-labor-estimates/:id', async () => {
    const body = { cost_cents: 12500, description: 'Updated estimate' };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        id: mockId,
        build_list_id: mockBuildListId,
        build_list_phase_id: null,
        name: 'Paint',
        description: body.description,
        cost_cents: body.cost_cents,
        sort_order: 0,
      },
    });

    const result = await buildListLaborEstimatesApi.updateLaborEstimate(
      mockId,
      body
    );

    expect(apiClient.put).toHaveBeenCalledWith(
      `/build-list-labor-estimates/${mockId}`,
      body
    );
    expect(result.data.cost_cents).toBe(body.cost_cents);
  });

  it('deleteLaborEstimate DELETEs /build-list-labor-estimates/:id', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: {
        id: mockId,
        build_list_id: mockBuildListId,
        build_list_phase_id: null,
        name: 'Paint',
        description: null,
        cost_cents: 50000,
        sort_order: 0,
      },
    });

    const result = await buildListLaborEstimatesApi.deleteLaborEstimate(mockId);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/build-list-labor-estimates/${mockId}`
    );
    expect(result.data.id).toBe(mockId);
  });
});
