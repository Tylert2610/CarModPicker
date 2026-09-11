/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/**
 * Tests for carGenerationsApi.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { carGenerationsApi } from './car_generations';
import { mockCar } from '../test/mocks/api';

describe('carGenerationsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCar GETs /car-generations/:id', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockCar });

    const result = await carGenerationsApi.getCar(mockCar.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/car-generations/${mockCar.id}`
    );
    expect(result.data).toEqual(mockCar);
  });

  it('listCars GETs /car-generations/ with default undefined params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.listCars();

    expect(apiClient.get).toHaveBeenCalledWith('/car-generations/', {
      params: undefined,
    });
  });

  it('listCars GETs /car-generations/ forwarding skip/limit/search', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.listCars({ skip: 10, limit: 25, search: 'Toyota' });

    expect(apiClient.get).toHaveBeenCalledWith('/car-generations/', {
      params: expect.objectContaining({
        skip: 10,
        limit: 25,
        search: 'Toyota',
      }),
    });
  });

  it('searchCars GETs /car-generations/search with q param and no pagination', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.searchCars('Camry');

    expect(apiClient.get).toHaveBeenCalledWith('/car-generations/search', {
      params: expect.objectContaining({ q: 'Camry' }),
    });
  });

  it('searchCars GETs /car-generations/search merging pagination params with q', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.searchCars('Camry', { skip: 5, limit: 10 });

    expect(apiClient.get).toHaveBeenCalledWith('/car-generations/search', {
      params: expect.objectContaining({
        q: 'Camry',
        skip: 5,
        limit: 10,
      }),
    });
  });

  it('getCarsByMake GETs /car-generations/car-makes/:make with encoded make', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.getCarsByMake('Alfa Romeo', { skip: 0, limit: 20 });

    expect(apiClient.get).toHaveBeenCalledWith(
      '/car-generations/car-makes/Alfa%20Romeo',
      {
        params: expect.objectContaining({ skip: 0, limit: 20 }),
      }
    );
  });

  it('getCarsByMake works with undefined pagination params', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.getCarsByMake('Toyota');

    expect(apiClient.get).toHaveBeenCalledWith(
      '/car-generations/car-makes/Toyota',
      { params: undefined }
    );
  });

  it('getCarsByMakeModel GETs nested URL with both segments encoded', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.getCarsByMakeModel('Alfa Romeo', 'Giulia GTA', {
      skip: 0,
      limit: 20,
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      '/car-generations/car-makes/Alfa%20Romeo/car-models/Giulia%20GTA',
      { params: expect.objectContaining({ skip: 0, limit: 20 }) }
    );
  });

  it('getCarsByIds GETs /car-generations/by-ids with ids array param', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [mockCar] });

    await carGenerationsApi.getCarsByIds([mockCar.id, 'another-id']);

    expect(apiClient.get).toHaveBeenCalledWith('/car-generations/by-ids', {
      params: expect.objectContaining({
        ids: [mockCar.id, 'another-id'],
      }),
    });
  });

  it('getCarMakeStats GETs /car-generations/stats/car-makes', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { Toyota: 12, Honda: 8 },
    });

    const result = await carGenerationsApi.getCarMakeStats();

    expect(apiClient.get).toHaveBeenCalledWith(
      '/car-generations/stats/car-makes'
    );
    expect(result.data).toEqual({ Toyota: 12, Honda: 8 });
  });

  it('countCars GETs /car-generations/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 150 } });

    const result = await carGenerationsApi.countCars();

    expect(apiClient.get).toHaveBeenCalledWith('/car-generations/count');
    expect(result.data).toEqual({ count: 150 });
  });

  it('countMakes GETs /car-generations/car-makes/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 30 } });

    const result = await carGenerationsApi.countMakes();

    expect(apiClient.get).toHaveBeenCalledWith(
      '/car-generations/car-makes/count'
    );
    expect(result.data).toEqual({ count: 30 });
  });

  it('countCarModels GETs /car-generations/car-models/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 75 } });

    const result = await carGenerationsApi.countCarModels();

    expect(apiClient.get).toHaveBeenCalledWith(
      '/car-generations/car-models/count'
    );
    expect(result.data).toEqual({ count: 75 });
  });
});
