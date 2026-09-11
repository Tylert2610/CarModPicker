import { describe, expect, it, vi } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import Support from './Support';

vi.mock('../hooks/useIsPremium', () => ({
  useIsPremium: () => false,
  useIsPremiumSystemDisabled: () => false,
}));

describe('Support page', () => {
  it('renders the Support CarModPicker heading', () => {
    render(<Support />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /support carmodpicker/i })
    ).toBeInTheDocument();
  });

  it('renders support option cards including Buy Me a Coffee link', () => {
    render(<Support />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /buy me a coffee/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /subscribe to premium/i })
    ).toBeInTheDocument();
  });
});
