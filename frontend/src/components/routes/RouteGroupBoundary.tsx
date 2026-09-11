import * as Sentry from '@sentry/react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '../ui/button';

/**
 * The four route groups the app wraps in their own error boundaries.
 */
export type RouteGroupName = 'admin' | 'authentication' | 'builder' | 'public';

/**
 * Wraps one route group in a Sentry error boundary so a throw inside it does
 * not blank the app, and surfaces the eventId with Retry and Go Home.
 */
export function RouteGroupBoundary({
  groupName,
  children,
}: {
  groupName: RouteGroupName;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <Sentry.ErrorBoundary
      beforeCapture={(scope) => scope.setTag('route_group', groupName)}
      fallback={(errorData) => {
        const { error, eventId } = errorData;
        const handleRetry = () => {
          errorData.resetError();
        };
        const handleGoHome = () => {
          void navigate('/');
        };
        return (
          <section
            data-route-group={groupName}
            className="container mx-auto px-4 py-16"
          >
            <div className="mx-auto max-w-lg p-8 bg-card/50 rounded-xl text-foreground">
              <h2 className="text-2xl font-semibold text-foreground mb-3">
                Something went wrong in the {groupName} section
              </h2>
              <p className="text-sm text-muted-foreground mb-2">
                {error instanceof Error ? error.message : 'Unknown error'}
              </p>
              <p className="text-xs text-muted-foreground mb-6">
                Event ID: <code className="font-mono">{eventId}</code>
              </p>
              <div className="flex gap-3">
                <Button type="button" onClick={handleRetry}>
                  Retry
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleGoHome}
                >
                  Go Home
                </Button>
              </div>
            </div>
          </section>
        );
      }}
    >
      {children}
    </Sentry.ErrorBoundary>
  );
}

export default RouteGroupBoundary;
