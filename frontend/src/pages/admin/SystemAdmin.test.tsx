// Phase 8 plan 08-16 (Wave 4) — SystemAdmin admin page coverage.
//
// SystemAdmin imports `adminApi` from `../../api/admin`, `appSettingsApi`
// from `../../api/app_settings` and `imageApi` from `../../api/images`, and
// also consumes `useAppSettings` (AppSettingsContext). Each of those modules
// calls the apiClient that setup.ts mocks.
//
// `useAppSettings` is mocked directly to avoid wiring an AppSettingsProvider
// (matches the Support.test.tsx precedent — mock the hook rather than the
// context layer). `useAuth` is mocked the same way.
//
// Covers the major sections enumerated in 08-PATTERNS.md §11 + plan 08-16
// task 2: Global App Settings toggle, Database Migrations run, Data
// Initialization (init car generations), and the destructive operations.

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { testScenarios } from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';

// Use the canonical admin scenario fixture for the authenticated-admin user.
const adminUser = testScenarios.adminAuthenticated.initialAuthState.user;

const mockSetAppSettings = vi.fn();

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../../hooks/useAppSettings', () => ({
  useAppSettings: () => ({
    settings: {
      premium_disabled: false,
      updated_at: '2026-04-24T00:00:00Z',
    },
    isLoading: false,
    refresh: vi.fn(),
    setSettings: mockSetAppSettings,
  }),
}));

import SystemAdmin from './SystemAdmin';

describe('SystemAdmin page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: adminUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
    // Default: current-revision fetch resolves to a known rev string.
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { current_revision: 'abc123' },
    });
  });

  it('renders the page header and all major section headings for admin', async () => {
    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /system & database/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole('heading', { name: /global app settings/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /database migrations/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /data initialization/i })
    ).toBeInTheDocument();

    // On mount, fetchCurrentRevision fires — assert the GET landed.
    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/admin/db-ops/migrations/current'
      )
    );
  });

  it('toggles the premium-system kill switch via appSettingsApi.update', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { premium_disabled: true, updated_at: '2026-04-24T00:01:00Z' },
    });

    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    // The checkbox for "Disconnect premium system" — find by the label text.
    const premiumLabel = screen.getByText(/disconnect premium system/i);
    const toggle = premiumLabel
      .closest('label')!
      .querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(toggle).not.toBeNull();

    await user.click(toggle);

    await waitFor(() =>
      expect(vi.mocked(apiClient.put)).toHaveBeenCalledWith(
        '/app-settings/',
        expect.objectContaining({ premium_disabled: true })
      )
    );
    expect(mockSetAppSettings).toHaveBeenCalled();
  });

  it('runs database migrations when the "Run Migrations" button is clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        success: true,
        output: 'alembic: ok',
        error: null,
        current_revision: 'def456',
      },
    });

    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    const runMigrations = await screen.findByRole('button', {
      name: /run migrations/i,
    });
    await user.click(runMigrations);

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/admin/db-ops/migrations/run'
      )
    );
    // Success message renders after resolution.
    await waitFor(() =>
      expect(
        screen.getByText(/migrations completed successfully/i)
      ).toBeInTheDocument()
    );
  });

  it('initializes car generations from the Data Initialization section', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { success: true, message: 'Seeded 42 generations.' },
    });

    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    const initButton = await screen.findByRole('button', {
      name: /init car generations/i,
    });
    await user.click(initButton);

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/admin/db-ops/init/car-generations'
      )
    );
    await waitFor(() =>
      expect(
        screen.getByText(/car generations: seeded 42 generations/i)
      ).toBeInTheDocument()
    );
  });

  it('lists orphaned bucket objects from the destructive-ops section', async () => {
    const user = userEvent.setup();
    // First GET is for current_revision (auto-fired). Queue a second GET for
    // the orphan-listing click — use mockResolvedValueOnce chained via the
    // default resolver.
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/images/admin/orphaned') {
        return Promise.resolve({
          data: {
            count: 2,
            total_bucket: 100,
            total_referenced: 98,
            orphaned_keys: ['users/a.jpg', 'users/b.jpg'],
          },
        });
      }
      return Promise.resolve({ data: { current_revision: 'abc123' } });
    });

    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    // Open the <details> wrapping destructive ops so the inner buttons render.
    const summary = screen.getByText(/deletion options \(cars, global parts/i);
    await user.click(summary);

    const listButton = await screen.findByRole('button', {
      name: /list orphaned \(dry run\)/i,
    });
    await user.click(listButton);

    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/images/admin/orphaned'
      )
    );
    // Result summary shows count 2.
    await waitFor(() =>
      expect(screen.getByText(/orphaned object\(s\) of/i)).toBeInTheDocument()
    );
  });

  it('denies access to authenticated non-admin user', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser, // is_admin: false
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    expect(
      screen.getByText(
        /you do not have permission to access the admin dashboard/i
      )
    ).toBeInTheDocument();
  });

  it('shows a login prompt when no user is authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <SystemAdmin />
      </BrowserRouter>
    );

    expect(
      screen.getByText(/please log in to access the admin dashboard/i)
    ).toBeInTheDocument();
  });
});
