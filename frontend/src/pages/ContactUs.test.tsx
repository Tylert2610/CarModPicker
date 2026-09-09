// Phase 8 plan 08-14 (D-11) — ContactUs page render test.
//
// ContactUs (as of this plan) is a static contact-info page — no form, no API
// call. The three mailto: links (Business, Tech Support, DMCA) are the only
// interactive surface. Cover headings + at least one mailto link + at least
// one alternate-section heading to satisfy the "at least 2 it-blocks" rule.

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
    // Hero subtitle tagline — also appears in body copy ("We'd love to hear
    // from you. Have questions, ..."), so match via getAllByText.
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

    // At least one mailto: link is wired. There are multiple (one per section).
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
