import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

/**
 * Covers ErrorBoundary: the styled fallback replaces the children tree on a
 * throw and the error reaches Sentry.captureException.
 */

const { mockedCapture } = vi.hoisted(() => ({
  mockedCapture: vi.fn(),
}));

vi.mock('@sentry/react', () => ({
  captureException: mockedCapture,
}));

import ErrorBoundary from './ErrorBoundary';

function Thrower(): ReactNode {
  throw new Error('boom');
}

function Safe(): ReactNode {
  return <div>all good</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error is thrown and does NOT call Sentry', () => {
    mockedCapture.mockClear();
    render(
      <ErrorBoundary>
        <Safe />
      </ErrorBoundary>
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
    expect(mockedCapture).not.toHaveBeenCalled();
  });

  it('renders fallback UI and reports to Sentry when a child throws', () => {
    mockedCapture.mockClear();

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Thrower />
      </ErrorBoundary>
    );

    expect(mockedCapture).toHaveBeenCalledTimes(1);
    const call = mockedCapture.mock.calls[0] as [
      Error,
      { extra: { componentStack: string } },
    ];
    const [errorArg, extraArg] = call;
    expect(errorArg).toBeInstanceOf(Error);
    expect(errorArg.message).toBe('boom');
    expect(typeof extraArg.extra.componentStack).toBe('string');
    expect(extraArg).toMatchObject({
      extra: { componentStack: expect.any(String) as unknown },
    });

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    errorSpy.mockRestore();
  });
});
