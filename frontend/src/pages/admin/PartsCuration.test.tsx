import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import {
  makeCurationCandidate,
  makeCurationQueue,
} from '../../test/mocks/admin/curation';
import { mockAdminUser, mockUseAuth } from '../../test/utils/test-mocks';
import { mockUser } from '../../test/mocks/api';
import PartsCuration from './PartsCuration';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

function seedAdmin(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    user: mockAdminUser,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

function seedNonAdmin(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    user: mockUser,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

describe('PartsCuration page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({
      data: makeCurationQueue(),
    });
    vi.mocked(apiClient.post).mockResolvedValue({ data: null });
  });

  it('renders the curation page with static sections for an admin user', () => {
    seedAdmin();
    render(
      <MemoryRouter initialEntries={['/admin/parts-curation']}>
        <PartsCuration />
      </MemoryRouter>
    );

    expect(screen.getByText('Parts Curation')).toBeInTheDocument();
    expect(screen.getByText(/Look up a link group/i)).toBeInTheDocument();
    expect(screen.getByText(/Manual link/i)).toBeInTheDocument();
    expect(screen.getByText(/Catalog rescan/i)).toBeInTheDocument();
  });

  it('loads a link group on lookup and renders members with Promote + Unlink', async () => {
    seedAdmin();
    const canonical = makeCurationCandidate({
      id: 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa',
      name: 'Canonical Part',
      is_canonical: true,
    });
    const duplicate = makeCurationCandidate({
      id: 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb',
      name: 'Duplicate Part',
      is_canonical: false,
    });
    vi.mocked(apiClient.get).mockResolvedValue({
      data: makeCurationQueue([canonical, duplicate]),
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/parts-curation']}>
        <PartsCuration />
      </MemoryRouter>
    );

    const partIdInput = screen.getByPlaceholderText(/Paste any Part ID/i);
    await user.type(partIdInput, canonical.id);
    await user.click(screen.getByRole('button', { name: /^Load group$/i }));

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        `/admin/parts/${canonical.id}/link-group`
      )
    );

    expect(await screen.findByText('Canonical Part')).toBeInTheDocument();
    expect(screen.getByText('Duplicate Part')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Promote/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Unlink/i })).toBeInTheDocument();
  });

  it('approves (promotes) a duplicate to canonical via adminApi.promotePartToCanonical', async () => {
    seedAdmin();
    const canonical = makeCurationCandidate({
      id: 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa',
      name: 'Original Canonical',
      is_canonical: true,
    });
    const duplicate = makeCurationCandidate({
      id: 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb',
      name: 'Duplicate to Promote',
      is_canonical: false,
    });
    vi.mocked(apiClient.get).mockResolvedValue({
      data: makeCurationQueue([canonical, duplicate]),
    });
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeCurationQueue([
        { ...duplicate, is_canonical: true },
        { ...canonical, is_canonical: false },
      ]),
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/parts-curation']}>
        <PartsCuration />
      </MemoryRouter>
    );

    await user.type(
      screen.getByPlaceholderText(/Paste any Part ID/i),
      canonical.id
    );
    await user.click(screen.getByRole('button', { name: /^Load group$/i }));
    expect(await screen.findByText('Duplicate to Promote')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Promote/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/admin/parts/promote-canonical',
        { part_id: duplicate.id }
      )
    );
  });

  it('merges a duplicate into a canonical via adminApi.manuallyLinkParts', async () => {
    seedAdmin();
    const duplicateId = 'cccccccc-cccc-7ccc-8ccc-cccccccccc01';
    const canonicalId = 'cccccccc-cccc-7ccc-8ccc-cccccccccc02';

    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeCurationQueue([
        makeCurationCandidate({
          id: canonicalId,
          name: 'Target Canonical',
          is_canonical: true,
        }),
        makeCurationCandidate({
          id: duplicateId,
          name: 'Source Duplicate',
          is_canonical: false,
        }),
      ]),
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/parts-curation']}>
        <PartsCuration />
      </MemoryRouter>
    );

    const duplicateInput = screen.getByPlaceholderText(
      /Part to become the duplicate/i
    );
    const canonicalInput = screen.getByPlaceholderText(/Target canonical/i);
    await user.type(duplicateInput, duplicateId);
    await user.type(canonicalInput, canonicalId);
    await user.click(
      screen.getByRole('button', { name: /Link as duplicate/i })
    );

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/admin/parts/link', {
        duplicate_id: duplicateId,
        canonical_id: canonicalId,
      })
    );

    await waitFor(() =>
      expect(screen.getByText(/Linked .* as duplicate of/i)).toBeInTheDocument()
    );
  });

  it('denies access with a permission error for a non-admin user', () => {
    seedNonAdmin();
    render(
      <MemoryRouter initialEntries={['/admin/parts-curation']}>
        <PartsCuration />
      </MemoryRouter>
    );

    expect(
      screen.getByText(/do not have permission to access this page/i)
    ).toBeInTheDocument();

    expect(screen.queryByText(/Look up a link group/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Manual link/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Catalog rescan/i)).not.toBeInTheDocument();
  });
});
