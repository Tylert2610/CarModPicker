/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import { mockBuildList, mockUser } from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import Builder from './Builder';

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

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

describe('Builder page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the build list grid when the user has build lists', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        data: [{ ...mockBuildList, total_votes: 3, total_cost_cents: 25000 }],
        pagination: {
          current_page: 1,
          total_pages: 1,
          total_items: 1,
          items_per_page: 8,
          has_next: false,
          has_previous: false,
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/builder']}>
        <Builder />
      </MemoryRouter>
    );

    expect(screen.getByText('Builder')).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

    expect(screen.getByText(/Create New Build List/i)).toBeInTheDocument();

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/build-lists/with-votes',
      expect.objectContaining({
        params: expect.objectContaining({ owner_id: mockUser.id }),
      })
    );
  });

  it('renders the empty state when the user has no build lists', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        data: [],
        pagination: {
          current_page: 1,
          total_pages: 0,
          total_items: 0,
          items_per_page: 8,
          has_next: false,
          has_previous: false,
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/builder']}>
        <Builder />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/don't have any build lists yet/i)
      ).toBeInTheDocument()
    );

    expect(screen.getByText(/Create New Build List/i)).toBeInTheDocument();
  });
});
