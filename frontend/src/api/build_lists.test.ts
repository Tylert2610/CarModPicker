/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/**
 * Tests for buildListsApi.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListsApi } from './build_lists';
import { mockBuildList, mockCar, mockUser } from '../test/mocks/api';

describe('buildListsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('createBuildList POSTs body to /build-lists/', async () => {
    const body = {
      name: 'New Build',
      description: 'desc',
      car_id: mockCar.id,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...mockBuildList, ...body },
    });

    const result = await buildListsApi.createBuildList(body);

    expect(apiClient.post).toHaveBeenCalledWith('/build-lists/', body);
    expect(result.data).toMatchObject(body);
  });

  it('getBuildList GETs /build-lists/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockBuildList });

    const result = await buildListsApi.getBuildList(mockBuildList.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}`
    );
    expect(result.data).toEqual(mockBuildList);
  });

  it('updateBuildList PUTs body to /build-lists/:id', async () => {
    const body = { name: 'Updated Name' };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { ...mockBuildList, ...body },
    });

    await buildListsApi.updateBuildList(mockBuildList.id, body);

    expect(apiClient.put).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}`,
      body
    );
  });

  it('deleteBuildList DELETEs /build-lists/:id', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: mockBuildList });

    await buildListsApi.deleteBuildList(mockBuildList.id);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}`
    );
  });

  it('listBuildLists GETs /build-lists/ with default params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockBuildList] });

    await buildListsApi.listBuildLists();

    expect(apiClient.get).toHaveBeenCalledWith('/build-lists/', {
      params: undefined,
    });
  });

  it('listBuildLists GETs /build-lists/ with search + pagination params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockBuildList] });

    await buildListsApi.listBuildLists({ skip: 10, limit: 25, search: 'abc' });

    expect(apiClient.get).toHaveBeenCalledWith('/build-lists/', {
      params: expect.objectContaining({
        skip: 10,
        limit: 25,
        search: 'abc',
      }),
    });
  });

  it('getBuildListsWithVotes GETs /build-lists/with-votes with filter params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        data: [],
        pagination: {
          current_page: 1,
          total_pages: 0,
          total_items: 0,
          items_per_page: 20,
          has_next: false,
          has_previous: false,
        },
      },
    });

    await buildListsApi.getBuildListsWithVotes({
      car_id: mockCar.id,
      sort: 'votes',
      min_cost_cents: 100,
    });

    expect(apiClient.get).toHaveBeenCalledWith('/build-lists/with-votes', {
      params: expect.objectContaining({
        car_id: mockCar.id,
        sort: 'votes',
        min_cost_cents: 100,
      }),
    });
  });

  it('getBuildListsByCar GETs nested /build-lists/car/:carId URL', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        data: [mockBuildList],
        pagination: {
          current_page: 1,
          total_pages: 1,
          total_items: 1,
          items_per_page: 20,
          has_next: false,
          has_previous: false,
        },
      },
    });

    await buildListsApi.getBuildListsByCar(mockCar.id, {
      skip: 0,
      limit: 20,
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-lists/car/${mockCar.id}`,
      { params: { skip: 0, limit: 20 } }
    );
  });

  it('getBuildListsByUser GETs nested /build-lists/user/:userId URL', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockBuildList] });

    await buildListsApi.getBuildListsByUser(mockUser.id, { limit: 5 });

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-lists/user/${mockUser.id}`,
      { params: { limit: 5 } }
    );
  });

  it('countBuildLists GETs /build-lists/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 42 } });

    const result = await buildListsApi.countBuildLists();

    expect(apiClient.get).toHaveBeenCalledWith('/build-lists/count');
    expect(result.data).toEqual({ count: 42 });
  });

  it('copyBuildList POSTs to nested /build-lists/:id/copy with new_name payload', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockBuildList });

    await buildListsApi.copyBuildList(mockBuildList.id, 'My Copy');

    expect(apiClient.post).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}/copy`,
      { new_name: 'My Copy' }
    );
  });

  it('copyBuildList defaults new_name to null when omitted', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockBuildList });

    await buildListsApi.copyBuildList(mockBuildList.id);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}/copy`,
      { new_name: null }
    );
  });

  it('getPhases GETs /build-lists/:id/phases', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await buildListsApi.getPhases(mockBuildList.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}/phases`
    );
  });

  it('createPhase POSTs body to /build-lists/:id/phases', async () => {
    const body = { name: 'Stage 1', sort_order: 0 };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa',
        build_list_id: mockBuildList.id,
        name: body.name,
        sort_order: body.sort_order,
      },
    });

    await buildListsApi.createPhase(mockBuildList.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}/phases`,
      body
    );
  });
});
