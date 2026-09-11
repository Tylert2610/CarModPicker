import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import TermsOfService from './TermsOfService';

describe('TermsOfService page', () => {
  it('renders the Terms of Service heading and last-updated stamp', () => {
    render(<TermsOfService />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /terms of service/i })
    ).toBeInTheDocument();
    const lastUpdated = screen.getAllByText(/last updated/i);
    expect(lastUpdated.length).toBeGreaterThan(0);
  });

  it('renders the Service section describing the agreement', () => {
    render(<TermsOfService />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /the service/i })
    ).toBeInTheDocument();
  });
});
