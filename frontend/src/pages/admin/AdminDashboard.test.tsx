import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import AdminDashboard from './AdminDashboard';

const nonAdminAuthenticated = {
  initialAuthState: {
    isAuthenticated: true,
    user: { ...mockUser, is_admin: false },
    isLoading: false,
  },
};

describe('AdminDashboard page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the dashboard heading and all admin section cards for an admin user', () => {
    render(<AdminDashboard />, testScenarios.adminAuthenticated);

    expect(
      screen.getByRole('heading', { level: 1, name: /admin dashboard/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: /admin sections/i })
    ).toBeInTheDocument();

    const sectionTitles = [
      'User Management',
      'Report Review',
      'Bug Reports',
      'Crawler & Jobs',
      'Parts Curation',
      'System & Database',
      'System Statistics',
    ];
    for (const title of sectionTitles) {
      expect(
        screen.getByRole('heading', { level: 3, name: title })
      ).toBeInTheDocument();
    }

    const buttons = screen.getAllByRole('button', {
      name: new RegExp(sectionTitles.join('|'), 'i'),
    });
    expect(buttons.length).toBe(sectionTitles.length);

    fireEvent.click(buttons[0]!);
  });

  it('denies access to an authenticated non-admin user', () => {
    render(<AdminDashboard />, nonAdminAuthenticated);

    expect(
      screen.getByText(
        /you do not have permission to access the admin dashboard/i
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByRole('heading', { level: 2, name: /admin sections/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { level: 3, name: /user management/i })
    ).not.toBeInTheDocument();
  });

  it('prompts an unauthenticated visitor to log in', () => {
    render(<AdminDashboard />, testScenarios.unauthenticated);

    expect(
      screen.getByText(/please log in to access the admin dashboard/i)
    ).toBeInTheDocument();

    expect(
      screen.queryByRole('heading', { level: 2, name: /admin sections/i })
    ).not.toBeInTheDocument();
  });
});
