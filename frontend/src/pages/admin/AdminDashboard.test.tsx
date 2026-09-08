// Phase 8 plan 08-15 (D-02 Wave 4) — AdminDashboard page coverage.
//
// AdminDashboard.tsx is a 131-line nav hub: if the user is null → "Please log
// in" ErrorAlert; if user exists but `is_admin === false` → "You do not have
// permission" ErrorAlert (plus a useEffect redirect to `/`); otherwise renders
// 7 admin section cards, each with an ActionButton that calls
// `navigate(section.path)`.
//
// Per PATTERNS.md §11 + plan 08-15 interfaces, we assert:
// 1. Admin happy path — heading + all 7 section titles + navigate-on-click.
// 2. Non-admin auth-deny path.
// 3. Unauthenticated (null user) login-prompt path.
//
// Mocking: setup.ts mocks `../../api/client` and test-utils.tsx mocks
// `../../hooks/useAuth`. No per-file mocks needed.
// We use `testScenarios.adminAuthenticated` (Phase 8 D-05, seeded by plan
// 08-01) for the admin fixture.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import AdminDashboard from './AdminDashboard';

// Non-admin authenticated scenario — built from the canonical typed `mockUser`
// to avoid the stale shape in `testScenarios.authenticated.initialAuthState.user`
// (it's produced by `createMockUser()` which predates the is_service_account /
// subscription_tier / subscription_status / totp_enabled fields on UserRead).
// Functionally equivalent to testScenarios.authenticated for our purposes —
// AdminDashboard only reads `user.is_admin`.
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

    // Top-level page header (h1) + section header (h2) both render.
    expect(
      screen.getByRole('heading', { level: 1, name: /admin dashboard/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: /admin sections/i })
    ).toBeInTheDocument();

    // All 7 admin-section card titles render as <h3>s.
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

    // Each card has an ActionButton (button, not link) labeled with the
    // section title — 7 buttons total.
    const buttons = screen.getAllByRole('button', {
      name: new RegExp(sectionTitles.join('|'), 'i'),
    });
    expect(buttons.length).toBe(sectionTitles.length);

    // Navigating does not throw (BrowserRouter handles the push).
    fireEvent.click(buttons[0]!);
  });

  it('denies access to an authenticated non-admin user', () => {
    render(<AdminDashboard />, nonAdminAuthenticated);

    // The non-admin branch renders the permission-denied ErrorAlert.
    expect(
      screen.getByText(
        /you do not have permission to access the admin dashboard/i
      )
    ).toBeInTheDocument();

    // None of the admin-section cards render.
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

    // Admin sections are not rendered for a null user either.
    expect(
      screen.queryByRole('heading', { level: 2, name: /admin sections/i })
    ).not.toBeInTheDocument();
  });
});
