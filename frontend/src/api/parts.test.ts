/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { partsApi } from './parts';
import { mockCar, mockCategory, mockPart } from '../test/mocks/api';
import type { PartCreate, PartUpdate } from '../types/Api';

describe('partsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getParts GETs /parts/ with default undefined params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    const result = await partsApi.getParts();

    expect(apiClient.get).toHaveBeenCalledWith('/parts/', {
      params: undefined,
    });
    expect(result.data).toEqual([mockPart]);
  });

  it('getParts GETs /parts/ forwarding filter params (search, car_id, category_id, skip, limit)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await partsApi.getParts({
      skip: 0,
      limit: 50,
      category_id: mockCategory.id,
      car_id: mockCar.id,
      search: 'intake',
    });

    expect(apiClient.get).toHaveBeenCalledWith('/parts/', {
      params: expect.objectContaining({
        skip: 0,
        limit: 50,
        category_id: mockCategory.id,
        car_id: mockCar.id,
        search: 'intake',
      }),
    });
  });

  it('getPartsWithVotes GETs /parts/with-votes with default undefined params', async () => {
    const paginated = {
      data: [],
      pagination: {
        current_page: 1,
        total_pages: 0,
        total_items: 0,
        items_per_page: 20,
        has_next: false,
        has_previous: false,
      },
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: paginated });

    const result = await partsApi.getPartsWithVotes();

    expect(apiClient.get).toHaveBeenCalledWith('/parts/with-votes', {
      params: undefined,
    });
    expect(result.data).toEqual(paginated);
  });

  it('getPartsWithVotes GETs /parts/with-votes forwarding rich filter params', async () => {
    const paginated = {
      data: [],
      pagination: {
        current_page: 1,
        total_pages: 0,
        total_items: 0,
        items_per_page: 20,
        has_next: false,
        has_previous: false,
      },
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: paginated });

    await partsApi.getPartsWithVotes({
      category_ids: [mockCategory.id],
      car_ids: [mockCar.id],
      part_manufacturer_ids: ['pm-1'],
      sort: 'votes',
      min_price_cents: 100,
      max_price_cents: 99999,
      universal: false,
      search: 'coilover',
    });

    expect(apiClient.get).toHaveBeenCalledWith('/parts/with-votes', {
      params: expect.objectContaining({
        category_ids: [mockCategory.id],
        car_ids: [mockCar.id],
        part_manufacturer_ids: ['pm-1'],
        sort: 'votes',
        min_price_cents: 100,
        max_price_cents: 99999,
        universal: false,
        search: 'coilover',
      }),
    });
  });

  it('getFilterOptions GETs /parts/filter-options with default undefined params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { category_ids: [], part_manufacturer_ids: [] },
    });

    await partsApi.getFilterOptions();

    expect(apiClient.get).toHaveBeenCalledWith('/parts/filter-options', {
      params: undefined,
    });
  });

  it('getFilterOptions forwards category_ids/car_ids/search/user_id/universal', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        category_ids: [mockCategory.id],
        part_manufacturer_ids: ['pm-1'],
        car_ids: [mockCar.id],
      },
    });

    await partsApi.getFilterOptions({
      category_ids: [mockCategory.id],
      part_manufacturer_ids: ['pm-1'],
      car_ids: [mockCar.id],
      search: 'brake',
      user_id: 'user-1',
      universal: true,
    });

    expect(apiClient.get).toHaveBeenCalledWith('/parts/filter-options', {
      params: expect.objectContaining({
        category_ids: [mockCategory.id],
        part_manufacturer_ids: ['pm-1'],
        car_ids: [mockCar.id],
        search: 'brake',
        user_id: 'user-1',
        universal: true,
      }),
    });
  });

  it('getPartsByCategory GETs /parts/category/:categoryId with filter_id injected into params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await partsApi.getPartsByCategory(mockCategory.id, { skip: 5, limit: 20 });

    expect(apiClient.get).toHaveBeenCalledWith(
      `/parts/category/${mockCategory.id}`,
      {
        params: expect.objectContaining({
          filter_id: mockCategory.id,
          skip: 5,
          limit: 20,
        }),
      }
    );
  });

  it('getPartsByCategory works with no pagination params (filter_id still present)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await partsApi.getPartsByCategory(mockCategory.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/parts/category/${mockCategory.id}`,
      {
        params: expect.objectContaining({ filter_id: mockCategory.id }),
      }
    );
  });

  it('createPart POSTs body to /parts/', async () => {
    const body: PartCreate = {
      name: 'New Part',
      category_id: mockCategory.id,
      part_manufacturer_id: 'pm-1',
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...mockPart, ...body },
    });

    const result = await partsApi.createPart(body);

    expect(apiClient.post).toHaveBeenCalledWith('/parts/', body);
    expect(result.data).toMatchObject(body);
  });

  it('getPart GETs /parts/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockPart });

    const result = await partsApi.getPart(mockPart.id);

    expect(apiClient.get).toHaveBeenCalledWith(`/parts/${mockPart.id}`);
    expect(result.data).toEqual(mockPart);
  });

  it('getPartListings GETs /parts/:id/listings', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await partsApi.getPartListings(mockPart.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/parts/${mockPart.id}/listings`
    );
  });

  it('getPartPriceHistorySummary forwards window to GET /parts/:id/price-history with object response type', async () => {
    const summary = {
      summary: {
        min_cents: 1000,
        max_cents: 2000,
        last_cents: 1500,
        last_observed_at: '2026-04-01T00:00:00Z',
        trend: 'flat' as const,
        observation_count: 5,
      },
      retailers: [],
      history: [],
      window: '90d',
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: summary });

    const result = await partsApi.getPartPriceHistorySummary(mockPart.id, {
      window: '90d',
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      `/parts/${mockPart.id}/price-history`,
      { params: expect.objectContaining({ window: '90d' }) }
    );
    expect(result.data).toEqual(summary);
    expect(Array.isArray(result.data)).toBe(false);
  });

  it('getPartPriceHistorySummary forwards retailer_id when provided', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        summary: {
          min_cents: null,
          max_cents: null,
          last_cents: null,
          last_observed_at: null,
          trend: 'flat',
          observation_count: 0,
        },
        retailers: [],
        history: [],
        window: '30d',
      },
    });

    await partsApi.getPartPriceHistorySummary(mockPart.id, {
      window: '30d',
      retailer_id: 'r-2',
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      `/parts/${mockPart.id}/price-history`,
      {
        params: expect.objectContaining({
          window: '30d',
          retailer_id: 'r-2',
        }),
      }
    );
  });

  it('getBatchPriceHistorySummary POSTs body to /parts/price-history', async () => {
    const body = {
      part_ids: [mockPart.id, 'p-2', 'p-3'],
      window: '90d' as const,
    };
    const responseBody = {
      summaries: {},
      window: '90d',
      requested_count: 3,
      found_count: 0,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: responseBody });

    const result = await partsApi.getBatchPriceHistorySummary(body);

    expect(apiClient.post).toHaveBeenCalledWith('/parts/price-history', body);
    expect(result.data).toEqual(responseBody);
  });

  it('updatePart PUTs body to /parts/:id', async () => {
    const body: PartUpdate = {
      name: 'Updated Name',
      part_manufacturer_id: 'pm-1',
    };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { ...mockPart, ...body },
    });

    await partsApi.updatePart(mockPart.id, body);

    expect(apiClient.put).toHaveBeenCalledWith(`/parts/${mockPart.id}`, body);
  });

  it('deletePart DELETEs /parts/:id', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: mockPart });

    await partsApi.deletePart(mockPart.id);

    expect(apiClient.delete).toHaveBeenCalledWith(`/parts/${mockPart.id}`);
  });

  it('appendPartImages POSTs file_keys body to /parts/:id/append-images', async () => {
    const fileKeys = ['key-1', 'key-2'];
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockPart });

    await partsApi.appendPartImages(mockPart.id, fileKeys);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/parts/${mockPart.id}/append-images`,
      { file_keys: fileKeys }
    );
  });

  it('removePartImage DELETEs /parts/:id/images/:index', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: mockPart });

    await partsApi.removePartImage(mockPart.id, 2);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/parts/${mockPart.id}/images/2`
    );
  });

  it('setPartPrimaryImage PATCHes index body to /parts/:id/primary-image', async () => {
    vi.mocked(apiClient.patch).mockResolvedValueOnce({ data: mockPart });

    await partsApi.setPartPrimaryImage(mockPart.id, 3);

    expect(apiClient.patch).toHaveBeenCalledWith(
      `/parts/${mockPart.id}/primary-image`,
      { index: 3 }
    );
  });

  it('countParts GETs /parts/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 42 } });

    const result = await partsApi.countParts();

    expect(apiClient.get).toHaveBeenCalledWith('/parts/count');
    expect(result.data).toEqual({ count: 42 });
  });

  it('countPartsByUser GETs /parts/user/:userId/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 7 } });

    await partsApi.countPartsByUser(mockPart.user_id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/parts/user/${mockPart.user_id}/count`
    );
  });

  it('checkProductUrl GETs /parts/check-url with product_url param', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { existing_part_id: mockPart.id },
    });

    const result = await partsApi.checkProductUrl(
      'https://retailer.example/abc'
    );

    expect(apiClient.get).toHaveBeenCalledWith('/parts/check-url', {
      params: expect.objectContaining({
        product_url: 'https://retailer.example/abc',
      }),
    });
    expect(result.data).toEqual({ existing_part_id: mockPart.id });
  });

  it('checkProductUrl returns null existing_part_id when no match', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { existing_part_id: null },
    });

    const result = await partsApi.checkProductUrl('https://new.example/xyz');

    expect(result.data.existing_part_id).toBeNull();
  });
});
