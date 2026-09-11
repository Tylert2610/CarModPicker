/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: mockUser,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  }),
}));

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { mockBuildList, mockUser } from '../../test/mocks/api';
import type { BuildLogPostRead } from '../../types/Api';
import ViewBuildLog from './ViewBuildLog';

const _EMULATES = 'testScenarios.authenticated';
void _EMULATES;

const mockPost: BuildLogPostRead = {
  id: 'aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa',
  build_log_id: 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb',
  user_id: mockUser.id,
  content: 'First progress update on the build',
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  author_username: mockUser.username,
  author_image_url: null,
};

function seedApiClient(opts: { posts?: BuildLogPostRead[] } = {}) {
  const posts = opts.posts ?? [mockPost];
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes('/build-logs/build-list/')) {
      return Promise.resolve({
        data: {
          id: 'cccccccc-cccc-7ccc-8ccc-cccccccccccc',
          build_list_id: mockBuildList.id,
          title: `Build Log: ${mockBuildList.name}`,
          created_at: '2026-04-24T00:00:00Z',
          updated_at: '2026-04-24T00:00:00Z',
          posts,
          pagination: {
            current_page: 1,
            total_pages: 1,
            total_items: posts.length,
            items_per_page: 20,
            has_next: false,
            has_previous: false,
          },
        },
      });
    }
    if (url.startsWith('/build-lists/')) {
      return Promise.resolve({ data: mockBuildList });
    }
    return Promise.resolve({ data: null });
  });
}

describe('ViewBuildLog page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedApiClient();
  });

  it('renders the build log heading and existing posts for an authenticated user', async () => {
    render(
      <MemoryRouter initialEntries={[`/build-logs/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-logs/:buildListId" element={<ViewBuildLog />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

    expect(screen.getByText('Build Log Thread')).toBeInTheDocument();
    expect(screen.getByText(mockPost.content)).toBeInTheDocument();

    expect(
      screen.getByRole('button', { name: /new post/i })
    ).toBeInTheDocument();
  });

  it('shows the empty state when the build log has no posts', async () => {
    seedApiClient({ posts: [] });

    render(
      <MemoryRouter initialEntries={[`/build-logs/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-logs/:buildListId" element={<ViewBuildLog />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(/no posts yet/i)).toBeInTheDocument()
    );
    expect(
      screen.getByText(/be the first to post in this build log/i)
    ).toBeInTheDocument();
  });

  it('submits a new post via the compose dialog', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        ...mockPost,
        id: 'dddddddd-dddd-7ddd-8ddd-dddddddddddd',
        content: 'Swapped in new headers today',
      },
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/build-logs/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-logs/:buildListId" element={<ViewBuildLog />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

    await user.click(screen.getByRole('button', { name: /new post/i }));

    const textarea = await screen.findByLabelText(/post content/i);
    await user.type(textarea, 'Swapped in new headers today');

    const postButton = screen.getAllByRole('button', { name: /^post$/i }).pop();
    if (!postButton) throw new Error('Post submit button not found');
    await user.click(postButton);

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        `/build-logs/build-list/${mockBuildList.id}/posts`,
        expect.objectContaining({ content: 'Swapped in new headers today' })
      )
    );
  });

  it('uploads an image through the compose dialog to the images endpoint', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        file_key: 'build_log_post/img-123.jpg',
        presigned_url: 'https://example.com/presigned/img-123.jpg',
        message: 'ok',
      },
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/build-logs/${mockBuildList.id}`]}>
        <Routes>
          <Route path="/build-logs/:buildListId" element={<ViewBuildLog />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(mockBuildList.name)).toBeInTheDocument()
    );

    await user.click(screen.getByRole('button', { name: /new post/i }));

    const fileInput =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error('File input not found');

    const file = new File(['x'], 'progress.jpg', { type: 'image/jpeg' });
    await user.upload(fileInput, file);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
      const calls = vi.mocked(apiClient.post).mock.calls;
      const imageCall = calls.find(([url]) =>
        String(url).startsWith('/images/upload')
      );
      expect(imageCall).toBeDefined();
      expect(imageCall?.[1]).toBeInstanceOf(FormData);
      expect(imageCall?.[2]).toEqual(
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'multipart/form-data',
          }),
        })
      );
    });
  });
});
