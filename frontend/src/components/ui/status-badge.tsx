import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '../../lib/utils';

const statusBadgeVariants = cva(
  'inline-flex items-center rounded px-2 py-1 text-xs font-medium',
  {
    variants: {
      variant: {
        pending: 'bg-warning/15 text-warning',
        in_progress: 'bg-info/15 text-info',
        resolved: 'bg-success/15 text-success',
        dismissed: 'bg-muted text-muted-foreground',
      },
    },
    defaultVariants: {
      variant: 'pending',
    },
  }
);

const statusLabels: Record<NonNullable<StatusBadgeProps['variant']>, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
};

/** Props for StatusBadge: span attributes plus a status variant. */
export interface StatusBadgeProps
  extends
    Omit<React.HTMLAttributes<HTMLSpanElement>, 'children'>,
    VariantProps<typeof statusBadgeVariants> {
  variant: 'pending' | 'in_progress' | 'resolved' | 'dismissed';
  children?: React.ReactNode;
  ref?: React.Ref<HTMLSpanElement>;
}

/** A small pill showing a record's status, labelled from its variant. */
export function StatusBadge({
  className,
  variant,
  children,
  ref,
  ...props
}: StatusBadgeProps) {
  return (
    <span
      ref={ref}
      className={cn(statusBadgeVariants({ variant }), className)}
      {...props}
    >
      {children ?? statusLabels[variant]}
    </span>
  );
}

const priorityBadgeVariants = cva(
  'inline-flex items-center rounded px-2 py-1 text-xs font-medium',
  {
    variants: {
      priority: {
        low: 'bg-muted text-muted-foreground',
        medium: 'bg-warning/15 text-warning',
        high: 'bg-warning/25 text-warning-foreground',
        critical: 'bg-destructive/15 text-destructive',
      },
    },
    defaultVariants: {
      priority: 'medium',
    },
  }
);

const priorityLabels: Record<
  NonNullable<PriorityBadgeProps['priority']>,
  string
> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

/** Props for PriorityBadge: span attributes plus a priority variant. */
export interface PriorityBadgeProps
  extends
    Omit<React.HTMLAttributes<HTMLSpanElement>, 'children'>,
    VariantProps<typeof priorityBadgeVariants> {
  priority: 'low' | 'medium' | 'high' | 'critical';
  children?: React.ReactNode;
  ref?: React.Ref<HTMLSpanElement>;
}

/** A small pill showing a priority level, labelled from its variant. */
export function PriorityBadge({
  className,
  priority,
  children,
  ref,
  ...props
}: PriorityBadgeProps) {
  return (
    <span
      ref={ref}
      className={cn(priorityBadgeVariants({ priority }), className)}
      {...props}
    >
      {children ?? priorityLabels[priority]}
    </span>
  );
}
