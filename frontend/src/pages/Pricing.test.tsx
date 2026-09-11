import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Pricing from './Pricing';

describe('Pricing page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders the Simple Pricing heading and both tier cards (unauthenticated)', () => {
    render(
      <BrowserRouter>
        <Pricing />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /simple pricing/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /^free$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /^premium$/i })
    ).toBeInTheDocument();
  });

  it('routes unauthenticated users to /register via the Premium CTA', () => {
    render(
      <BrowserRouter>
        <Pricing />
      </BrowserRouter>
    );
    const goPremium = screen.getByRole('link', { name: /go premium/i });
    expect(goPremium).toHaveAttribute('href', '/register');
  });

  it('routes authenticated users to /checkout via the Premium CTA', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <Pricing />
      </BrowserRouter>
    );
    const goPremium = screen.getByRole('link', { name: /go premium/i });
    expect(goPremium).toHaveAttribute('href', '/checkout');
  });
});
