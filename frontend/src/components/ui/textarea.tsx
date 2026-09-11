import * as React from 'react';

import { cn } from '../../lib/utils';

/** Props for Textarea: textarea attributes plus an error flag. */
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
  ref?: React.Ref<HTMLTextAreaElement>;
}

/** A multi-line text input matching the Input styling. */
export function Textarea({ className, error, ref, ...props }: TextareaProps) {
  return (
    <textarea
      ref={ref}
      aria-invalid={error || undefined}
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-destructive aria-[invalid=true]:focus-visible:ring-destructive',
        className
      )}
      {...props}
    />
  );
}
