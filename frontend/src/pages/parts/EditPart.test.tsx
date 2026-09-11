import type { ReactElement, ReactNode } from 'react';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { mockCategory, mockPart, mockUser } from '../../test/mocks/api';
import type { UserRead } from '../../types/Api';
import EditPart from './EditPart';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

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

const mockFullPart = {
  ...mockPart,
  category_id: mockCategory.id,
  part_manufacturer_id: MOCK_MANUFACTURER_ID,
};

describe('EditPart page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    await waitFor(() => {
      expect(screen.getByText(/edit test part/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue(mockPart.name)).toBeInTheDocument();
    });

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

    const submit = screen.getByRole('button', { name: /update part/i });
    await user.click(submit);

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith(
        `/parts/${mockFullPart.id}`,
        expect.objectContaining({ name: 'Updated Part' })
      );
    });

    expect(vi.mocked(apiClient.put).mock.calls.length).toBe(1);
    expect((nameField as HTMLInputElement).value).toBe('Updated Part');
  });

  it('denies edit access and shows a permission error for a non-owner viewer', async () => {
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

    expect(screen.queryByDisplayValue(mockPart.name)).not.toBeInTheDocument();
  });
});
