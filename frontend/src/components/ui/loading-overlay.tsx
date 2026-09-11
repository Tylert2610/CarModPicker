import * as React from 'react';
import { Loader2 } from 'lucide-react';

import { cn } from '../../lib/utils';

/** Props for LoadingOverlay: div attributes plus a visibility flag. */
export interface LoadingOverlayProps extends React.HTMLAttributes<HTMLDivElement> {
  visible: boolean;
  label?: string;
  ref?: React.Ref<HTMLDivElement>;
}

/** A translucent cover with a spinner, shown over content while it loads. */
export function LoadingOverlay({
  className,
  visible,
  label,
  ref,
  ...props
}: LoadingOverlayProps) {
  if (!visible) return null;
  return (
    <div
      ref={ref}
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        'absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/80 backdrop-blur-sm',
        className
      )}
      {...props}
    >
      <div className="flex flex-col items-center gap-2 text-foreground">
        <Loader2
          className="h-6 w-6 animate-spin text-primary"
          aria-hidden="true"
        />
        {label ? (
          <p className="text-sm text-muted-foreground">{label}</p>
        ) : (
          <span className="sr-only">Loading…</span>
        )}
      </div>
    </div>
  );
}
