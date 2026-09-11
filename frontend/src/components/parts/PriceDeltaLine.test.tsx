import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PriceDeltaLine from './PriceDeltaLine';
import type { PriceHistorySummary } from '../../types/Api';

function makeSummary(
  overrides: Partial<PriceHistorySummary> = {}
): PriceHistorySummary {
  return {
    min_cents: 4500,
    max_cents: 5500,
    last_cents: 5000,
    last_observed_at: '2026-04-01T00:00:00Z',
    trend: 'flat',
    observation_count: 5,
    ...overrides,
  };
}

describe('PriceDeltaLine', () => {
  it('renders nothing when summary is null', () => {
    const { container } = render(<PriceDeltaLine summary={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when summary is undefined', () => {
    const { container } = render(<PriceDeltaLine summary={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when observation_count is zero', () => {
    const { container } = render(
      <PriceDeltaLine
        summary={makeSummary({
          observation_count: 0,
          min_cents: null,
          max_cents: null,
          last_cents: null,
          last_observed_at: null,
          trend: 'flat',
        })}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders "Tracked since <date>" for a single observation', () => {
    render(
      <PriceDeltaLine
        summary={makeSummary({
          observation_count: 1,
          min_cents: 5000,
          max_cents: 5000,
          last_cents: 5000,
          last_observed_at: '2026-04-01T12:00:00Z',
          trend: 'flat',
        })}
      />
    );
    expect(screen.getByTestId('price-delta-line').textContent).toMatch(
      /Tracked since/
    );
  });

  it('renders min → max for multiple observations', () => {
    render(
      <PriceDeltaLine
        summary={makeSummary({
          observation_count: 8,
          min_cents: 4500,
          max_cents: 5500,
          trend: 'down',
        })}
      />
    );
    const text = screen.getByTestId('price-delta-line').textContent ?? '';
    expect(text).toContain('$45');
    expect(text).toContain('$55');
    expect(text).toContain('→');
  });

  it('rounds cents to whole dollars in the min/max output', () => {
    render(
      <PriceDeltaLine
        summary={makeSummary({
          observation_count: 4,
          min_cents: 4949,
          max_cents: 5550,
          trend: 'up',
        })}
      />
    );
    const text = screen.getByTestId('price-delta-line').textContent ?? '';
    expect(text).toContain('$49');
    expect(text).toContain('$56');
  });

  it('uses ↑ arrow for trend=up', () => {
    render(<PriceDeltaLine summary={makeSummary({ trend: 'up' })} />);
    expect(screen.getByTestId('price-delta-arrow').textContent).toBe('↑');
  });

  it('uses ↓ arrow for trend=down', () => {
    render(<PriceDeltaLine summary={makeSummary({ trend: 'down' })} />);
    expect(screen.getByTestId('price-delta-arrow').textContent).toBe('↓');
  });

  it('uses · arrow for trend=flat', () => {
    render(<PriceDeltaLine summary={makeSummary({ trend: 'flat' })} />);
    expect(screen.getByTestId('price-delta-arrow').textContent).toBe('·');
  });

  it('shows trend arrow on the single-observation variant too', () => {
    render(
      <PriceDeltaLine
        summary={makeSummary({
          observation_count: 1,
          trend: 'up',
        })}
      />
    );
    expect(screen.getByTestId('price-delta-arrow').textContent).toBe('↑');
  });
});
