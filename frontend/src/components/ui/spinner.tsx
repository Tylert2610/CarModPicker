import * as React from 'react';
import { Loader2 } from 'lucide-react';

import { cn } from '../../lib/utils';

/** The sizes a Spinner can render at. */
export type SpinnerSize = 'xs' | 'sm' | 'base' | 'md' | 'lg' | 'xl';

/** Props for Spinner: size and optional class overrides. */
export interface SpinnerProps {
  size?: SpinnerSize;
  className?: string;
  text?: string;
  inline?: boolean;
}

const sizeClasses: Record<SpinnerSize, string> = {
  xs: 'h-4 w-4',
  sm: 'h-4 w-4',
  base: 'h-5 w-5',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
  xl: 'h-12 w-12',
};

/** The app's loading spinner, at one of the named sizes. */
const Spinner: React.FC<SpinnerProps> = ({
  size = 'md',
  className,
  text,
  inline = false,
}) => {
  const icon = (
    <Loader2
      className={cn('animate-spin text-primary', sizeClasses[size])}
      aria-hidden="true"
    />
  );

  if (inline) {
    return icon;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn('flex flex-col items-center justify-center', className)}
    >
      {icon}
      {text ? (
        <p className="mt-3 animate-pulse text-sm text-muted-foreground">
          {text}
        </p>
      ) : (
        <span className="sr-only">Loading…</span>
      )}
    </div>
  );
};

export default Spinner;
