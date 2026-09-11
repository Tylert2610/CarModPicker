import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

class ResizeObserverStub {
  constructor(_cb: ResizeObserverCallback) {
    void _cb;
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

import { apiClient } from '../../api/client';
import {
  mockCategory,
  mockPart,
  mockUser,
  mockVoteSummary,
} from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import ViewPart from './ViewPart';

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

function installDefaultGetRouting(): void {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === `/parts/${mockPart.id}`) {
      return Promise.resolve({ data: mockPart });
    }
    if (url === `/votes/part/${mockPart.id}/summary`) {
      return Promise.resolve({ data: mockVoteSummary });
    }
    if (url === '/categories/') {
      return Promise.resolve({ data: [mockCategory] });
    }
    if (url === `/users/${mockUser.id}`) {
      return Promise.resolve({ data: mockUser });
    }
    if (url === `/parts/${mockPart.id}/listings`) {
      return Promise.resolve({ data: [] });
    }
    if (url === `/parts/${mockPart.id}/price-history`) {
      return Promise.resolve({ data: [] });
    }
    return Promise.resolve({ data: null });
  });
}

describe('ViewPart page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the part name and canonical fetches once data resolves', async () => {
    installDefaultGetRouting();

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: mockPart.name })
      ).toBeInTheDocument()
    );

    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/parts/${mockPart.id}`
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/votes/part/${mockPart.id}/summary`
    );
  });

  it('renders the Community Rating vote widget with upvote + downvote buttons', async () => {
    installDefaultGetRouting();

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText('Community Rating')).toBeInTheDocument()
    );

    expect(screen.getByRole('button', { name: /upvote/i })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /downvote/i })
    ).toBeInTheDocument();

    expect(screen.getByText('+4')).toBeInTheDocument();
  });

  it('renders a manufacturer as plain text (no link)', async () => {
    const ugcMfrId = 'pm-ugc-1111-7111-8111-111111111111';
    const ugcMfrName = 'UserSubmittedBrand';
    const partWithUgcMfr = { ...mockPart, part_manufacturer_id: ugcMfrId };

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/parts/${mockPart.id}`) {
        return Promise.resolve({ data: partWithUgcMfr });
      }
      if (url === `/votes/part/${mockPart.id}/summary`) {
        return Promise.resolve({ data: mockVoteSummary });
      }
      if (url === '/categories/') {
        return Promise.resolve({ data: [mockCategory] });
      }
      if (url === `/users/${mockUser.id}`) {
        return Promise.resolve({ data: mockUser });
      }
      if (url === `/parts/${mockPart.id}/listings`) {
        return Promise.resolve({ data: [] });
      }
      if (url === `/parts/${mockPart.id}/price-history`) {
        return Promise.resolve({ data: [] });
      }
      if (url === `/part-manufacturers/${ugcMfrId}`) {
        return Promise.resolve({
          data: {
            id: ugcMfrId,
            name: ugcMfrName,
            description: null,
            is_active: true,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(ugcMfrName)).toBeInTheDocument()
    );
    const links = screen
      .queryAllByRole('link')
      .filter((a) => a.getAttribute('href')?.includes('part_manufacturer_id='));
    expect(links).toHaveLength(0);
  });

  it('posts to the vote endpoint when the user clicks a vote button', async () => {
    installDefaultGetRouting();
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { entity_id: mockPart.id, vote_type: 'downvote' },
    });

    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText('Community Rating')).toBeInTheDocument()
    );
    const downvoteButton = screen.getByRole('button', { name: /downvote/i });

    await user.click(downvoteButton);

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        `/votes/part/${mockPart.id}`,
        expect.objectContaining({ vote_type: 'downvote' })
      )
    );
  });
});
