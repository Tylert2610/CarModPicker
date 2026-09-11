/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockBuildList, mockPart, mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Search from './Search';

const searchResultsFixture = {
  data: {
    query: 'honda',
    build_lists: {
      data: [mockBuildList],
      total: 1,
      has_next: false,
      skip: 0,
      limit: 10,
    },
    users: {
      data: [mockUser],
      total: 1,
      has_next: false,
      skip: 0,
      limit: 10,
    },
    parts: {
      data: [mockPart],
      total: 1,
      has_next: false,
      skip: 0,
      limit: 10,
    },
  },
};

const emptyResultsFixture = {
  data: {
    query: 'missing',
    build_lists: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    users: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    parts: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
  },
};

describe('Search page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders the initial empty state when no query is in the URL', () => {
    render(
      <MemoryRouter initialEntries={['/search']}>
        <Search />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /^search$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/enter a search term to find build lists/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/search build lists and users/i)
    ).toBeInTheDocument();
  });

  it('renders search results from the API when query param is present', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(searchResultsFixture);

    render(
      <MemoryRouter initialEntries={['/search?q=honda']}>
        <Search />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/search/',
        expect.objectContaining({
          params: expect.objectContaining({ q: 'honda' }),
        })
      )
    );
  });

  it('shows a no-results message when the API returns empty result sets', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(emptyResultsFixture);

    render(
      <MemoryRouter initialEntries={['/search?q=missing']}>
        <Search />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/no results found for "missing"/i)
      ).toBeInTheDocument()
    );
  });
});
