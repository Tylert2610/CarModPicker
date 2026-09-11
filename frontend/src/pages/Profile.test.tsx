/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Profile from './Profile';

describe('Profile page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders authenticated user profile with username + email visible', async () => {
    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await waitFor(() =>
      expect(
        screen.getAllByText(new RegExp(mockUser.username)).length
      ).toBeGreaterThan(0)
    );
    expect(
      screen.getAllByText(new RegExp(mockUser.email)).length
    ).toBeGreaterThan(0);
  });

  it('uploads profile image via apiClient.post with FormData when user picks a file in edit mode', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        file_key: 'users/test/avatar.jpg',
        presigned_url: 'https://example.com/avatar-signed.jpg',
        message: 'ok',
      },
    });
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await user.click(screen.getByRole('button', { name: /edit profile/i }));

    const fileInput =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error('Could not find hidden file input');

    const file = new File(['hello'], 'avatar.jpg', { type: 'image/jpeg' });
    await user.upload(fileInput, file);

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        expect.stringContaining('/images/upload'),
        expect.any(FormData),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'multipart/form-data',
          }),
        })
      )
    );

    const call = vi
      .mocked(apiClient.post)
      .mock.calls.find(
        ([url]) => typeof url === 'string' && url.includes('/images/upload')
      );
    expect(call).toBeDefined();
    const fd: FormData = call?.[1] as FormData;
    expect(fd.get('file')).toBe(file);
  });

  it('shows an error when the image upload request fails', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(
      new Error('Upload failed: server error')
    );
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await user.click(screen.getByRole('button', { name: /edit profile/i }));

    const fileInput =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error('Could not find hidden file input');

    const file = new File(['hello'], 'avatar.jpg', { type: 'image/jpeg' });
    await user.upload(fileInput, file);

    await waitFor(() =>
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
    );
  });
});
