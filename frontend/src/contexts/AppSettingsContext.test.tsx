// Phase 8 plan 08-09 (D-10) — provider test for AppSettingsContext.
//
// Covers the provider-internal state transitions:
//   - initial mount fetch via appSettingsApi.get() resolves → settings populated
//   - fetch-failure path → settings remain null, isLoading flips to idle
//   - setSettings direct update → consumer re-renders with new value
//   - refresh() re-fetches settings (second apiClient call)
//
// The provider does NOT call useNavigate, so no MemoryRouter wrap is needed.
//
// The provider reads settings through `appSettingsApi` from
// `../api/app_settings`, so this file mocks that module directly and swaps its
// two methods for hoisted spies.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGet, mockUpdate } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockUpdate: vi.fn(),
}));

// Replace appSettingsApi's two methods with hoisted spies so the provider's
// fetch and refresh paths are observable, keeping the module's other exports.
vi.mock('../api/app_settings', async () => {
  const actual = await vi.importActual<typeof import('../api/app_settings')>(
    '../api/app_settings'
  );
  return {
    ...actual,
    appSettingsApi: {
      get: mockGet,
      update: mockUpdate,
    },
  };
});

import { AppSettingsProvider } from './AppSettingsContext';
import { useAppSettings } from '../hooks/useAppSettings';
import type { AppSettings } from '../api/app_settings';

const baseSettings: AppSettings = {
  premium_disabled: false,
  updated_at: '2026-04-24T00:00:00Z',
};

const disabledSettings: AppSettings = {
  premium_disabled: true,
  updated_at: '2026-04-24T01:00:00Z',
};

function Consumer() {
  const { settings, isLoading, refresh, setSettings } = useAppSettings();
  return (
    <div>
      <span data-testid="loading">{isLoading ? 'loading' : 'idle'}</span>
      <span data-testid="premium-disabled">
        {settings === null ? 'null' : settings.premium_disabled ? 'yes' : 'no'}
      </span>
      <span data-testid="updated-at">{settings?.updated_at ?? 'none'}</span>
      <button
        type="button"
        onClick={() => {
          void refresh();
        }}
      >
        refresh
      </button>
      <button
        type="button"
        onClick={() => {
          setSettings(disabledSettings);
        }}
      >
        setSettings
      </button>
    </div>
  );
}

function renderWithProvider(children: ReactNode = <Consumer />) {
  return render(<AppSettingsProvider>{children}</AppSettingsProvider>);
}

describe('AppSettingsContext provider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockReset();
    mockUpdate.mockReset();
  });

  it('fetches settings on mount and exposes them to consumers', async () => {
    mockGet.mockResolvedValueOnce({ data: baseSettings });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('idle')
    );

    expect(screen.getByTestId('premium-disabled').textContent).toBe('no');
    expect(screen.getByTestId('updated-at').textContent).toBe(
      baseSettings.updated_at
    );
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('leaves settings null and flips isLoading idle when the fetch rejects', async () => {
    mockGet.mockRejectedValueOnce(new Error('public endpoint unreachable'));

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('idle')
    );

    expect(screen.getByTestId('premium-disabled').textContent).toBe('null');
    expect(screen.getByTestId('updated-at').textContent).toBe('none');
  });

  it('setSettings updates the consumer view without refetching', async () => {
    mockGet.mockResolvedValueOnce({ data: baseSettings });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('premium-disabled').textContent).toBe('no')
    );

    fireEvent.click(screen.getByText('setSettings'));

    await waitFor(() =>
      expect(screen.getByTestId('premium-disabled').textContent).toBe('yes')
    );
    expect(screen.getByTestId('updated-at').textContent).toBe(
      disabledSettings.updated_at
    );
    // setSettings is a direct state mutation — the provider does NOT issue a
    // second GET.
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('refresh() re-fetches settings and replaces the cached value', async () => {
    mockGet
      .mockResolvedValueOnce({ data: baseSettings })
      .mockResolvedValueOnce({ data: disabledSettings });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('premium-disabled').textContent).toBe('no')
    );

    fireEvent.click(screen.getByText('refresh'));

    await waitFor(() =>
      expect(screen.getByTestId('premium-disabled').textContent).toBe('yes')
    );
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
