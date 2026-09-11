import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import { buildApiError } from '../../test/apiResponse';
import { mockBuildList, mockCar, mockUser } from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import ViewCar from './ViewCar';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

const authenticatedAuthState = {
  isAuthenticated: true,
  isLoading: false,
} as const;

function seedAuthenticated(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: authenticatedAuthState.isAuthenticated,
    user: mockUser,
    isLoading: authenticatedAuthState.isLoading,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

describe('ViewCar page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the car header, info card, and build lists section when the fetch succeeds', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.resolve({ data: mockCar });
      }
      if (url.startsWith(`/build-lists/car/${mockCar.id}`)) {
        return Promise.resolve({
          data: {
            data: [mockBuildList],
            pagination: {
              current_page: 1,
              total_pages: 1,
              total_items: 1,
              items_per_page: 10,
              has_next: false,
              has_previous: false,
            },
          },
        });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/car-generations/${mockCar.id}`]}>
        <Routes>
          <Route path="/car-generations/:carId" element={<ViewCar />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByRole('heading', {
          level: 1,
          name: new RegExp(mockCar.car_make_name),
        })
      ).toBeInTheDocument()
    );

    expect(screen.getByText('Make:')).toBeInTheDocument();
    expect(screen.getByText('Model:')).toBeInTheDocument();
    expect(screen.getByText('Generation:')).toBeInTheDocument();
    expect(screen.getByText('Year Range:')).toBeInTheDocument();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/car-generations/${mockCar.id}`
    );
  });

  it('renders an error alert when the car fetch rejects', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.reject(
          buildApiError(404, {
            success: false,
            status: 404,
            message: 'Car not found',
            request_id: 'req-1',
            error_code: 'NOT_FOUND',
          })
        );
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/car-generations/${mockCar.id}`]}>
        <Routes>
          <Route path="/car-generations/:carId" element={<ViewCar />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/Failed to load car with ID/i)
      ).toBeInTheDocument()
    );

    expect(
      screen.getByRole('heading', { name: /Car Details/i })
    ).toBeInTheDocument();
  });
});
