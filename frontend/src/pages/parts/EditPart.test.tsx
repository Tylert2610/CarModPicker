// Phase 8 Wave 3 page test — EditPart authenticates the owner, fetches the
// target part via partsApi.getPart, renders EditPartForm, and submits an
// edit through apiClient.put('/parts/:partId', ...).
//
// This file builds a local render that wraps children in
// <MemoryRouter>+<Routes> (EditPart reads partId via useParams) and seeds
// useAuth via the same mockUseAuth singleton test-utils uses, so the auth
// scenario is set per test without going through customRender.

import type { ReactElement, ReactNode } from 'react';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { mockCategory, mockPart, mockUser } from '../../test/mocks/api';
import type { UserRead } from '../../types/Api';
import EditPart from './EditPart';

// Mock useAuth the same way TestProviders does. The local seedAuth helper
// below is equivalent to calling render(..., testScenarios.authenticated) or
// testScenarios.unauthenticated from test-utils.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// EditPart and EditPartForm reach the API through their `../../api/<domain>`
// modules, which call the apiClient that setup.ts mocks, so assertions on
// `apiClient.put(...)` see the real call.

import { apiClient } from '../../api/client';

interface AuthState {
  isAuthenticated: boolean;
  user: UserRead | null;
  isLoading?: boolean;
}

const seedAuth = (state: AuthState) => {
  mockUseAuth.mockReturnValue({
    isAuthenticated: state.isAuthenticated,
    user: state.user,
    isLoading: state.isLoading ?? false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  });
};

// EditPart relies on useParams() — wrap in <Routes> with a matching path.
const renderAtEditRoute = (ui: ReactElement, partId: string = mockPart.id) =>
  rtlRender(ui, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={[`/parts/${partId}/edit`]}>
        <Routes>
          <Route path="/parts/:partId/edit" element={children} />
        </Routes>
      </MemoryRouter>
    ),
  });

// A mock part manufacturer that matches EditPartForm's PartManufacturerResponse shape.
const MOCK_MANUFACTURER_ID = 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa';
const mockManufacturer = {
  id: MOCK_MANUFACTURER_ID,
  name: 'TestPartManufacturer',
  description: null,
  image_urls: [],
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// A part that has all required fields populated — category_id matches
// mockCategory.id (so the <select required> option resolves) and
// part_manufacturer_id matches mockManufacturer (so the form's custom
// validation at EditPartForm.tsx:243 passes).
const mockFullPart = {
  ...mockPart,
  category_id: mockCategory.id,
  part_manufacturer_id: MOCK_MANUFACTURER_ID,
};

// The authenticated owner: mockPart.user_id matches mockUser.id
// ('11111111-1111-7111-8111-111111111111'), so canEdit is true without an
// admin flag.
describe('EditPart page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: /parts/:id returns the fully-populated part. Categories and
    // part-manufacturers return a single entry matching the part's ids so
    // the <select> and SearchableSelect can render a valid option.
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/parts/${mockPart.id}`) {
        return Promise.resolve({ data: mockFullPart });
      }
      if (url.startsWith('/categories')) {
        return Promise.resolve({ data: [mockCategory] });
      }
      if (url.startsWith('/car-generations')) {
        return Promise.resolve({ data: [] });
      }
      if (url.startsWith('/part-manufacturers')) {
        return Promise.resolve({ data: [mockManufacturer] });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it('renders EditPartForm with the fetched part name in its input', async () => {
    seedAuth({ isAuthenticated: true, user: mockUser });
    renderAtEditRoute(<EditPart />);

    // Page title hydrates from the fetched part: "Edit {part.name}".
    await waitFor(() => {
      expect(screen.getByText(/edit test part/i)).toBeInTheDocument();
    });

    // Part name is seeded into the Part Name input by EditPartForm's
    // useEffect [part] (EditPartForm.tsx:116-134). The form mount + that
    // effect can resolve one tick AFTER the title renders, so wrap the
    // assertion in waitFor to absorb the microtask gap.
    await waitFor(() => {
      expect(screen.getByDisplayValue(mockPart.name)).toBeInTheDocument();
    });

    // getPart was called with the route's :partId param.
    expect(apiClient.get).toHaveBeenCalledWith(`/parts/${mockPart.id}`);
  });

  it('submits edits via apiClient.put(/parts/:partId, ...)', async () => {
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: { ...mockFullPart, name: 'Updated Part' },
    });

    seedAuth({ isAuthenticated: true, user: mockUser });
    const user = userEvent.setup();
    renderAtEditRoute(<EditPart />);

    const nameField = await screen.findByDisplayValue(mockPart.name);
    await user.clear(nameField);
    await user.type(nameField, 'Updated Part');

    // Submit happy path — category_id + part_manufacturer_id are seeded
    // from mockFullPart, the backing <option> and SearchableSelect entries
    // match, so validation passes through to the PUT request.
    const submit = screen.getByRole('button', { name: /update part/i });
    await user.click(submit);

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith(
        `/parts/${mockFullPart.id}`,
        expect.objectContaining({ name: 'Updated Part' })
      );
    });

    // Exactly one PUT fired, and the display value reflects the edit.
    expect(vi.mocked(apiClient.put).mock.calls.length).toBe(1);
    expect((nameField as HTMLInputElement).value).toBe('Updated Part');
  });

  it('denies edit access and shows a permission error for a non-owner viewer', async () => {
    // A different authenticated user (not the owner, not admin) — canEdit is
    // false and EditPart.tsx:98 renders the "no permission" ErrorAlert.
    const strangerUser: UserRead = {
      ...mockUser,
      id: '99999999-9999-7999-8999-999999999999',
      is_admin: false,
      is_superuser: false,
    };

    seedAuth({ isAuthenticated: true, user: strangerUser });
    renderAtEditRoute(<EditPart />);

    await waitFor(() => {
      expect(
        screen.getByText(/don't have permission to edit this part/i)
      ).toBeInTheDocument();
    });

    // Form did NOT render (no Part Name input seeded).
    expect(screen.queryByDisplayValue(mockPart.name)).not.toBeInTheDocument();
  });
});
