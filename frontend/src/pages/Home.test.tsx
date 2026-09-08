// Phase 8 plan 08-14 (D-11) — Home page happy-path + auth-branch tests.
//
// Home pulls named domain APIs (buildListsApi/partsApi/retailersApi/
// partManufacturersApi) from their `../api/<domain>` modules, which route
// through the apiClient that setup.ts mocks, so assertions land on
// vi.mocked(apiClient.get) without a per-file module mock.
//
// We render manually with BrowserRouter plus an inline mockUseAuth setup
// rather than through test-utils.tsx's customRender, so this file controls the
// auth branch directly.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Home from './Home';

describe('Home page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] });
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders the CarModPicker hero + unauthenticated CTAs (Get Started + Sign In)', () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /carmodpicker/i })
    ).toBeInTheDocument();
    const getStarted = screen.getByRole('link', { name: /get started/i });
    expect(getStarted).toHaveAttribute('href', '/register');
    const signIn = screen.getByRole('link', { name: /sign in/i });
    expect(signIn).toHaveAttribute('href', '/login');
  });

  it('renders authenticated hero CTA (Create Build) when user is logged in', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    // Hero "Create Build" CTA links to /builder.
    const createBuildLinks = screen.getAllByRole('link', {
      name: /create build/i,
    });
    expect(createBuildLinks.length).toBeGreaterThan(0);
    expect(createBuildLinks[0]).toHaveAttribute('href', '/builder');
  });

  it('renders Featured Builds section heading', () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /featured builds/i })
    ).toBeInTheDocument();
  });

  it('fires off the initial API fetches on mount', async () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );
    await waitFor(() => expect(vi.mocked(apiClient.get)).toHaveBeenCalled());
  });
});
