import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';

import { RouteGroupBoundary } from './RouteGroupBoundary';

/**
 * Covers RouteGroupBoundary: containment, the eventId / Retry / Go Home
 * fallback, and the data-route-group attribute other tests query. Uses the real
 * @sentry/react so the surfaced eventId is genuine.
 */

function Thrower(): ReactNode {
  throw new Error('kaboom');
}

function Safe(): ReactNode {
  return <div>safe content</div>;
}

describe('RouteGroupBoundary', () => {
  let errorSpy: MockInstance<typeof console.error>;

  beforeEach(() => {
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it('renders children when no error is thrown', () => {
    render(
      <MemoryRouter>
        <RouteGroupBoundary groupName="admin">
          <Safe />
        </RouteGroupBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText('safe content')).toBeInTheDocument();
    expect(document.querySelector('[data-route-group]')).toBeNull();
  });

  it('renders the fallback with event ID when a child throws', () => {
    render(
      <MemoryRouter>
        <RouteGroupBoundary groupName="builder">
          <Thrower />
        </RouteGroupBoundary>
      </MemoryRouter>
    );
    const section = document.querySelector('[data-route-group="builder"]');
    expect(section).not.toBeNull();
    expect(
      screen.getByText(/something went wrong in the builder section/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/kaboom/)).toBeInTheDocument();
    expect(screen.getByText(/event id:/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /go home/i })
    ).toBeInTheDocument();
  });

  it('Retry button calls resetError and re-renders non-throwing children', () => {
    let shouldThrow = true;
    function ConditionalThrower(): ReactNode {
      if (shouldThrow) throw new Error('boom');
      return <div>recovered</div>;
    }

    render(
      <MemoryRouter>
        <RouteGroupBoundary groupName="public">
          <ConditionalThrower />
        </RouteGroupBoundary>
      </MemoryRouter>
    );
    expect(
      document.querySelector('[data-route-group="public"]')
    ).not.toBeNull();

    shouldThrow = false;
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(screen.getByText('recovered')).toBeInTheDocument();
  });
});
