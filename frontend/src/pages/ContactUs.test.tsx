import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../api/client';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import ContactUs from './ContactUs';

const getMock = vi.mocked(apiClient.get);

describe('ContactUs page', () => {
  it('renders the Contact Us heading and hero copy', () => {
    render(<ContactUs />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /^contact us$/i })
    ).toBeInTheDocument();
    const tagline = screen.getAllByText(/we'd love to hear from you/i);
    expect(tagline.length).toBeGreaterThan(0);
  });

  it('renders business, tech support, and DMCA section headings with mailto links', () => {
    render(<ContactUs />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /business inquiries/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /tech support/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /dmca & copyright/i })
    ).toBeInTheDocument();

    const mailtoLinks = screen
      .getAllByRole('link')
      .filter((a) => a.getAttribute('href')?.startsWith('mailto:'));
    expect(mailtoLinks.length).toBeGreaterThanOrEqual(1);
  });

  it('does not call the API (pure static page with no form submit)', () => {
    render(<ContactUs />, testScenarios.unauthenticated);

    expect(vi.mocked(apiClient.post)).not.toHaveBeenCalled();
    expect(getMock).not.toHaveBeenCalled();
  });
});
