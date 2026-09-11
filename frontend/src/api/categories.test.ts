/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { categoriesApi } from './categories';
import { mockCategory, mockPart } from '../test/mocks/api';

describe('categoriesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCategories GETs /categories/', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCategory] });

    const result = await categoriesApi.getCategories();

    expect(apiClient.get).toHaveBeenCalledWith('/categories/');
    expect(result.data).toEqual([mockCategory]);
  });

  it('getCategory GETs /categories/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockCategory });

    const result = await categoriesApi.getCategory(mockCategory.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/categories/${mockCategory.id}`
    );
    expect(result.data).toEqual(mockCategory);
  });

  it('getPartsByCategory GETs /categories/:id/parts with undefined params by default', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await categoriesApi.getPartsByCategory(mockCategory.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/categories/${mockCategory.id}/parts`,
      { params: undefined }
    );
  });

  it('getPartsByCategory forwards skip/limit pagination params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockPart] });

    await categoriesApi.getPartsByCategory(mockCategory.id, {
      skip: 10,
      limit: 25,
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      `/categories/${mockCategory.id}/parts`,
      { params: expect.objectContaining({ skip: 10, limit: 25 }) }
    );
  });

  it('getCategoryPartsCount GETs /categories/:id/parts-count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 12 } });

    const result = await categoriesApi.getCategoryPartsCount(mockCategory.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/categories/${mockCategory.id}/parts-count`
    );
    expect(result.data).toEqual({ count: 12 });
  });

  it('countCategories GETs /categories/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 8 } });

    const result = await categoriesApi.countCategories();

    expect(apiClient.get).toHaveBeenCalledWith('/categories/count');
    expect(result.data).toEqual({ count: 8 });
  });
});
