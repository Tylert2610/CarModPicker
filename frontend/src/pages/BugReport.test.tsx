import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUseAuth } from '../test/utils/test-mocks';
import { mockUser } from '../test/mocks/api';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import BugReport from './BugReport';

describe('BugReport page', () => {
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

  it('renders the bug report form with title + description fields + submit button', () => {
    render(
      <MemoryRouter>
        <BugReport />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: /report a bug/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^description/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /submit bug report/i })
    ).toBeInTheDocument();
  });

  it('submits the form and calls bugReportsApi.createBugReport via apiClient.post', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { id: '11111111-1111-7111-8111-000000000001' },
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <BugReport />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/title/i), 'Test bug');
    await user.type(screen.getByLabelText(/^description/i), 'Description text');
    await user.click(
      screen.getByRole('button', { name: /submit bug report/i })
    );

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/bug-reports/',
        expect.objectContaining({
          title: 'Test bug',
          description: 'Description text',
        })
      )
    );
  });

  it('shows a validation error when title is empty (bypassing HTML5 required attr)', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <BugReport />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/^description/i), 'Some description');

    const form = document.querySelector('form');
    if (!form) throw new Error('No form element found');
    form.noValidate = true;

    await user.click(
      screen.getByRole('button', { name: /submit bug report/i })
    );

    await waitFor(() =>
      expect(screen.getByText(/title is required/i)).toBeInTheDocument()
    );
    expect(vi.mocked(apiClient.post)).not.toHaveBeenCalled();
  });
});
