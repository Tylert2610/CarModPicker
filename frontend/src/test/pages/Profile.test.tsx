import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render, testScenarios } from '../utils/test-utils';
import Profile from '../../pages/Profile';

// Mock the API client
vi.mock('../../services/Api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

describe('Profile', () => {
  it('renders profile page for authenticated user', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Profile')).toBeInTheDocument();
    });
  });

  it('displays user information when loaded', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });
  });

  it('shows loading state initially', async () => {
    render(<Profile />, testScenarios.loading);

    await waitFor(() => {
      // Look for the loading spinner by its class instead of test-id
      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  it('redirects unauthenticated users', async () => {
    render(<Profile />, testScenarios.unauthenticated);

    await waitFor(() => {
      // Should show error message for unauthenticated users
      expect(
        screen.getByText('User not found. Please log in.')
      ).toBeInTheDocument();
    });
  });

  it('displays profile sections', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Account Information')).toBeInTheDocument();
      expect(screen.getByText('Username:')).toBeInTheDocument();
      expect(screen.getByText('Email:')).toBeInTheDocument();
    });
  });

  it('shows edit profile form when edit mode is active', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      const editButton = screen.getByRole('button', { name: /edit profile/i });
      editButton.click();
    });

    await waitFor(() => {
      expect(screen.getByLabelText('Username')).toBeInTheDocument();
      expect(screen.getByLabelText('Email')).toBeInTheDocument();
    });
  });

  it('displays user profile picture section', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Profile Picture')).toBeInTheDocument();
    });
  });

  it('displays email verification status', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Email Verified')).toBeInTheDocument();
    });
  });

  it('displays account status', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Account Status')).toBeInTheDocument();
    });
  });

  it('shows manage subscription button', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Manage Subscription')).toBeInTheDocument();
    });
  });

  it('shows manage global parts button', async () => {
    render(<Profile />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Manage My Global Parts')).toBeInTheDocument();
    });
  });
});
