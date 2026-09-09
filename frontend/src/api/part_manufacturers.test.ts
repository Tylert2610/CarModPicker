// Phase 8 Wave 1 API-module test pattern (PATTERNS.md §7).
// `vi.mocked(apiClient.method)` and `expect(apiClient.method).toHaveBeenCalledWith(...)`
// both reference methods as unbound values; the eslint rule `@typescript-eslint/unbound-method`
// is a false positive here because vitest's mock runtime invokes them via the same
// `mockApiClient` object identity (see frontend/src/test/setup.ts dual-mock block).
/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { partManufacturersApi } from './part_manufacturers';
import { mockPart } from '../test/mocks/api';
import type {
  PartManufacturerCreate,
  PartManufacturerResponse,
  PartManufacturerUpdate,
} from '../types/Api';

const mockPartManufacturer: PartManufacturerResponse = {
  id: 'pm-1111-7111-8111-111111111111',
  name: 'TestPartManufacturer',
  description: 'Test description',
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('partManufacturersApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getPartManufacturers GETs /part-manufacturers/ with active_only=true default', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [mockPartManufacturer],
    });

    await partManufacturersApi.getPartManufacturers();

    expect(apiClient.get).toHaveBeenCalledWith('/part-manufacturers/', {
      params: expect.objectContaining({ active_only: true }),
    });
  });

  it('getPartManufacturers forwards active_only=false when caller opts in', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [mockPartManufacturer],
    });

    await partManufacturersApi.getPartManufacturers(false);

    expect(apiClient.get).toHaveBeenCalledWith('/part-manufacturers/', {
      params: expect.objectContaining({ active_only: false }),
    });
  });

  it('searchPartManufacturers GETs /part-manufacturers/search with q + pagination', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [mockPartManufacturer],
    });

    await partManufacturersApi.searchPartManufacturers('brembo', {
      skip: 0,
      limit: 10,
    });

    expect(apiClient.get).toHaveBeenCalledWith('/part-manufacturers/search', {
      params: expect.objectContaining({ q: 'brembo', skip: 0, limit: 10 }),
    });
  });

  it('searchPartManufacturers works with no pagination (q only)', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [mockPartManufacturer],
    });

    await partManufacturersApi.searchPartManufacturers('bilstein');

    expect(apiClient.get).toHaveBeenCalledWith('/part-manufacturers/search', {
      params: expect.objectContaining({ q: 'bilstein' }),
    });
  });

  it('getPartManufacturer GETs /part-manufacturers/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockPartManufacturer,
    });

    const result = await partManufacturersApi.getPartManufacturer(
      mockPartManufacturer.id
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      `/part-manufacturers/${mockPartManufacturer.id}`
    );
    expect(result.data).toEqual(mockPartManufacturer);
  });

  it('createPartManufacturer POSTs body to /part-manufacturers/', async () => {
    const body: PartManufacturerCreate = {
      name: 'NewPM',
      description: 'New PM description',
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...mockPartManufacturer, ...body },
    });

    await partManufacturersApi.createPartManufacturer(body);

    expect(apiClient.post).toHaveBeenCalledWith('/part-manufacturers/', body);
  });

  it('updatePartManufacturer PUTs body to /part-manufacturers/:id', async () => {
    const body: PartManufacturerUpdate = { name: 'RenamedPM' };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { ...mockPartManufacturer, ...body },
    });

    await partManufacturersApi.updatePartManufacturer(
      mockPartManufacturer.id,
      body
    );

    expect(apiClient.put).toHaveBeenCalledWith(
      `/part-manufacturers/${mockPartManufacturer.id}`,
      body
    );
  });

  it('deletePartManufacturer DELETEs /part-manufacturers/:id', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'deleted' },
    });

    await partManufacturersApi.deletePartManufacturer(mockPartManufacturer.id);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/part-manufacturers/${mockPartManufacturer.id}`
    );
  });

  it('getPartsByPartManufacturer GETs /part-manufacturers/:id/parts with undefined params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await partManufacturersApi.getPartsByPartManufacturer(
      mockPartManufacturer.id
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      `/part-manufacturers/${mockPartManufacturer.id}/parts`,
      { params: undefined }
    );
  });

  it('getPartsByPartManufacturer forwards pagination params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await partManufacturersApi.getPartsByPartManufacturer(
      mockPartManufacturer.id,
      { skip: 5, limit: 15 }
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      `/part-manufacturers/${mockPartManufacturer.id}/parts`,
      { params: expect.objectContaining({ skip: 5, limit: 15 }) }
    );
  });

  it('getPartManufacturerPartsCount GETs /part-manufacturers/:id/parts-count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { parts_count: 42 },
    });

    const result = await partManufacturersApi.getPartManufacturerPartsCount(
      mockPartManufacturer.id
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      `/part-manufacturers/${mockPartManufacturer.id}/parts-count`
    );
    expect(result.data).toEqual({ parts_count: 42 });
  });

  it('countPartManufacturers GETs /part-manufacturers/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 20 } });

    const result = await partManufacturersApi.countPartManufacturers();

    expect(apiClient.get).toHaveBeenCalledWith('/part-manufacturers/count');
    expect(result.data).toEqual({ count: 20 });
  });
});
