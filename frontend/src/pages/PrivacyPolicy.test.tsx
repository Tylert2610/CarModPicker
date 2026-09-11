import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import PrivacyPolicy from './PrivacyPolicy';

describe('PrivacyPolicy page', () => {
  it('renders the Privacy Policy heading and last-updated stamp', () => {
    render(<PrivacyPolicy />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /privacy policy/i })
    ).toBeInTheDocument();
    const lastUpdated = screen.getAllByText(/last updated/i);
    expect(lastUpdated.length).toBeGreaterThan(0);
  });

  it('renders the Information We Collect section', () => {
    render(<PrivacyPolicy />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /information we collect/i })
    ).toBeInTheDocument();
  });
});
