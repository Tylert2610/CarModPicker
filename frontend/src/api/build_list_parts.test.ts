/**
 * Tests for buildListPartsApi.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListPartsApi } from './build_list_parts';
import { mockBuildList, mockPart } from '../test/mocks/api';

describe('buildListPartsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('createPartAndAddToBuildList POSTs combined body to /build-list-parts/:id/create-and-add-part', async () => {
    const partData = {
      name: 'New Part',
      description: 'desc',
      image_urls: null,
      category_id: mockPart.category_id,
      car_ids: null,
      is_universal: false,
      part_manufacturer_id: 'mfg-id',
      part_number: 'PN-001',
      retailer_id: null,
      price_cents: 5000,
      product_url: null,
    };
    const buildListPartData = {
      part_id: null,
      quantity: 2,
      notes: 'extra notes',
      build_list_phase_id: null,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} });

    await buildListPartsApi.createPartAndAddToBuildList(
      mockBuildList.id,
      partData,
      buildListPartData
    );

    expect(apiClient.post).toHaveBeenCalledWith(
      `/build-list-parts/${mockBuildList.id}/create-and-add-part`,
      expect.objectContaining({
        name: 'New Part',
        description: 'desc',
        category_id: mockPart.category_id,
        part_manufacturer_id: 'mfg-id',
        part_number: 'PN-001',
        quantity: 2,
        notes: 'extra notes',
        is_universal: false,
      })
    );
  });

  it('addPartToBuildList POSTs to nested /build-list-parts/:id/parts/:part_id', async () => {
    const data = {
      part_id: mockPart.id,
      quantity: 1,
      notes: 'hello',
      build_list_phase_id: null,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} });

    await buildListPartsApi.addPartToBuildList(
      mockBuildList.id,
      mockPart.id,
      data
    );

    expect(apiClient.post).toHaveBeenCalledWith(
      `/build-list-parts/${mockBuildList.id}/parts/${mockPart.id}`,
      expect.objectContaining({
        part_id: mockPart.id,
        quantity: 1,
        notes: 'hello',
      })
    );
  });

  it('updateBuildListPart PUTs body to nested /build-list-parts/:id/parts/:part_id', async () => {
    const body = { quantity: 3, notes: 'updated' };
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: {} });

    await buildListPartsApi.updateBuildListPart(
      mockBuildList.id,
      mockPart.id,
      body
    );

    expect(apiClient.put).toHaveBeenCalledWith(
      `/build-list-parts/${mockBuildList.id}/parts/${mockPart.id}`,
      body
    );
  });

  it('updateBuildListPartById PUTs body to /build-list-parts/:blpId', async () => {
    const blpId = '66666666-6666-7666-8666-666666666666';
    const body = { purchased: true };
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: {} });

    await buildListPartsApi.updateBuildListPartById(blpId, body);

    expect(apiClient.put).toHaveBeenCalledWith(
      `/build-list-parts/${blpId}`,
      body
    );
  });

  it('removeBuildListPart DELETEs nested /build-list-parts/:id/parts/:part_id', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: {} });

    await buildListPartsApi.removeBuildListPart(mockBuildList.id, mockPart.id);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/build-list-parts/${mockBuildList.id}/parts/${mockPart.id}`
    );
  });

  it('deleteBuildListPartById DELETEs /build-list-parts/:blpId', async () => {
    const blpId = '77777777-7777-7777-8777-777777777777';
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: {} });

    await buildListPartsApi.deleteBuildListPartById(blpId);

    expect(apiClient.delete).toHaveBeenCalledWith(`/build-list-parts/${blpId}`);
  });

  it('getBuildListPartsBasic GETs /build-list-parts/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await buildListPartsApi.getBuildListPartsBasic(mockBuildList.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-list-parts/${mockBuildList.id}`
    );
  });

  it('getBuildListParts GETs /build-list-parts/:id/parts', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await buildListPartsApi.getBuildListParts(mockBuildList.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-list-parts/${mockBuildList.id}/parts`
    );
  });

  it('countBuildListsContainingPart GETs nested count URL for a part', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 7 } });

    const result = await buildListPartsApi.countBuildListsContainingPart(
      mockPart.id
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-list-parts/parts/${mockPart.id}/build-lists/count`
    );
    expect(result.data).toEqual({ count: 7 });
  });

  it('countBuildListParts GETs /build-list-parts/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 99 } });

    const result = await buildListPartsApi.countBuildListParts();

    expect(apiClient.get).toHaveBeenCalledWith('/build-list-parts/count');
    expect(result.data).toEqual({ count: 99 });
  });
});
