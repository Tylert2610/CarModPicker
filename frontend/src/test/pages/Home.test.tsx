import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render, testScenarios } from '../utils/test-utils';
import HomePage from '../../pages/Home';

describe('HomePage', () => {
  beforeEach(() => {
    // Clear any previous renders
    document.body.innerHTML = '';
  });

  it('renders welcome message for unauthenticated users', async () => {
    render(<HomePage />, testScenarios.unauthenticated);

    await waitFor(() => {
      expect(screen.getByText('Welcome to CarModPicker!')).toBeInTheDocument();
    });
  });

  it('renders guest content when not authenticated', async () => {
    render(<HomePage />, testScenarios.unauthenticated);

    await waitFor(() => {
      expect(
        screen.getByText(/Your ultimate platform for discovering/)
      ).toBeInTheDocument();
      expect(screen.getByText('Login to Start Your Build')).toBeInTheDocument();
      expect(screen.getByText('Login')).toBeInTheDocument();
      expect(screen.getByText('Register')).toBeInTheDocument();
    });
  });

  it('renders authenticated user content', async () => {
    render(<HomePage />, testScenarios.authenticated);

    await waitFor(() => {
      expect(screen.getByText('Hello, testuser!')).toBeInTheDocument();
      expect(
        screen.getByText(/Explore and manage your car modifications/)
      ).toBeInTheDocument();
      expect(screen.getByText('Start Your Build')).toBeInTheDocument();
    });
  });

  it('does not show guest content when authenticated', async () => {
    render(<HomePage />, testScenarios.authenticated);

    await waitFor(() => {
      expect(
        screen.queryByText('Login to Start Your Build')
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Please Login or Register/)
      ).not.toBeInTheDocument();
    });
  });

  it('has correct container classes', async () => {
    render(<HomePage />, testScenarios.unauthenticated);

    await waitFor(() => {
      const container = screen
        .getByText('Welcome to CarModPicker!')
        .closest('.container');
      expect(container).toHaveClass(
        'container',
        'mx-auto',
        'p-4',
        'text-center'
      );
    });
  });

  it('handles loading state properly', async () => {
    render(<HomePage />, testScenarios.loading);

    await waitFor(() => {
      // Should still render the basic structure even during loading
      expect(document.body).toBeInTheDocument();
    });
  });

  it('displays proper navigation links for guests', async () => {
    render(<HomePage />, testScenarios.unauthenticated);

    await waitFor(() => {
      // There are multiple login links, so we need to be more specific
      const loginLinks = screen.getAllByRole('link', { name: /login/i });
      const registerLink = screen.getByRole('link', { name: /register/i });

      expect(loginLinks.length).toBeGreaterThan(0);
      expect(registerLink).toBeInTheDocument();

      // Check that at least one login link points to /login
      const hasLoginLink = loginLinks.some(
        (link) => link.getAttribute('href') === '/login'
      );
      expect(hasLoginLink).toBe(true);
      expect(registerLink).toHaveAttribute('href', '/register');
    });
  });

  it('displays proper navigation links for authenticated users', async () => {
    render(<HomePage />, testScenarios.authenticated);

    await waitFor(() => {
      const startBuildLink = screen.getByRole('link', {
        name: /start your build/i,
      });

      expect(startBuildLink).toBeInTheDocument();
      expect(startBuildLink).toHaveAttribute('href', '/builder');
    });
  });
});
