/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get/post) is the canonical Phase 8 mocking pattern.
 */

// Phase 8 plan 08-18 (Wave 4 — D-02) — PartsCuration admin page test.
//
// PartsCuration is the admin canonical-part curation workflow page (762 lines).
// It uses adminApi (from ../../api/admin) for its core actions:
//   - getPartLinkGroup(partId)        — GET  /admin/parts/:id/link-group
//   - promotePartToCanonical(partId)  — POST /admin/parts/promote-canonical
//   - unlinkPartFromCanonical(partId) — POST /admin/parts/unlink
//   - manuallyLinkParts(body)         — POST /admin/parts/link (merge-canonical)
//   - rescanPartsForCanonicalLinking  — POST /admin/parts/rescan
//
// Coverage targets per plan 08-18:
//   1. Curation page render + static card structure for admin user
//   2. Link-group lookup + member row render (queue view)
//   3. Promote / approve action — adminApi.promotePartToCanonical
//   4. Merge-canonical action   — adminApi.manuallyLinkParts
//   5. Auth-deny for non-admin user
//
// We bypass test-utils.tsx's customRender because setupApiMocks() clears and
// re-installs default mock implementations inside customRender, which clobbers
// per-test `mockResolvedValueOnce` chains set in beforeEach. Follows the
// Builder.test.tsx + Profile.test.tsx pattern: local MemoryRouter + explicit
// `mockUseAuth.mockReturnValue(...)`, letting the real `adminApi` run so its
// internal apiClient.* calls land on the shared mock from setup.ts.

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

// Same rationale as Builder.test.tsx — test-utils.tsx registers the useAuth
// mock only when imported; this test doesn't import test-utils (we bypass
// customRender), so register the mock here against the same hook.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Logical equivalent of testScenarios.adminAuthenticated from test-utils.tsx.
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

// Logical equivalent of testScenarios.authenticated (non-admin user).
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
    // Default GET returns a single-canonical link group. Tests that need a
    // multi-member queue override with mockResolvedValueOnce BEFORE rendering.
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

    // Page header + all three admin cards render on first mount (no ?part= in URL).
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

    // Type a part id and click "Load group" — handleLookup calls
    // adminApi.getPartLinkGroup (GET /admin/parts/:id/link-group).
    const partIdInput = screen.getByPlaceholderText(/Paste any Part ID/i);
    await user.type(partIdInput, canonical.id);
    await user.click(screen.getByRole('button', { name: /^Load group$/i }));

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        `/admin/parts/${canonical.id}/link-group`
      )
    );

    // Both members render; Promote/Unlink only on non-canonical rows.
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

    // Load the link group so Promote buttons appear.
    await user.type(
      screen.getByPlaceholderText(/Paste any Part ID/i),
      canonical.id
    );
    await user.click(screen.getByRole('button', { name: /^Load group$/i }));
    expect(await screen.findByText('Duplicate to Promote')).toBeInTheDocument();

    // Click Promote on the only duplicate.
    await user.click(screen.getByRole('button', { name: /Promote/i }));

    // adminApi.promotePartToCanonical posts { part_id } to /admin/parts/promote-canonical.
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

    // Fill both manual-link inputs (Duplicate part ID + Canonical part ID) and
    // click "Link as duplicate". This is the merge-canonical user flow.
    const duplicateInput = screen.getByPlaceholderText(
      /Part to become the duplicate/i
    );
    const canonicalInput = screen.getByPlaceholderText(/Target canonical/i);
    await user.type(duplicateInput, duplicateId);
    await user.type(canonicalInput, canonicalId);
    await user.click(
      screen.getByRole('button', { name: /Link as duplicate/i })
    );

    // adminApi.manuallyLinkParts posts { duplicate_id, canonical_id } to
    // /admin/parts/link — the merge-canonical API surface.
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/admin/parts/link', {
        duplicate_id: duplicateId,
        canonical_id: canonicalId,
      })
    );

    // Success alert confirms the happy-path UI rendering post-merge.
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

    // Non-admin user hits the `!user.is_admin` branch — ErrorAlert renders
    // "You do not have permission to access this page."
    expect(
      screen.getByText(/do not have permission to access this page/i)
    ).toBeInTheDocument();

    // None of the admin action cards are rendered.
    expect(screen.queryByText(/Look up a link group/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Manual link/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Catalog rescan/i)).not.toBeInTheDocument();
  });
});
