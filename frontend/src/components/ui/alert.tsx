import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '../../lib/utils';

const alertVariants = cva(
  'relative w-full rounded-md border p-4 text-sm [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg+div]:translate-y-[-2px] [&>svg]:text-foreground [&>svg~*]:pl-7',
  {
    variants: {
      variant: {
        default: 'bg-background text-foreground border-border',
        destructive:
          'border-destructive/50 bg-destructive/10 text-destructive [&>svg]:text-destructive',
        success:
          'bg-success/10 text-success border-success/50 [&>svg]:text-success',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

/** Props for Alert: standard div attributes plus a visual variant. */
export interface AlertProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  ref?: React.Ref<HTMLDivElement>;
}

/** A bordered callout box with role="alert", styled by variant. */
export function Alert({ className, variant, ref, ...props }: AlertProps) {
  return (
    <div
      ref={ref}
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

/** The heading line inside an Alert. */
export function AlertTitle({
  className,
  ref,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & {
  ref?: React.Ref<HTMLParagraphElement>;
}) {
  return (
    <h5
      ref={ref}
      className={cn('mb-1 font-medium leading-none tracking-tight', className)}
      {...props}
    />
  );
}

/** The body text inside an Alert. */
export function AlertDescription({
  className,
  ref,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & {
  ref?: React.Ref<HTMLParagraphElement>;
}) {
  return (
    <div
      ref={ref}
      className={cn('text-sm [&_p]:leading-relaxed', className)}
      {...props}
    />
  );
}

interface MessageAlertProps {
  message: string | null;
}

/** A destructive-variant Alert for a message, rendering nothing when null. */
export const ErrorAlert: React.FC<MessageAlertProps> = ({ message }) => {
  if (!message) return null;
  return (
    <Alert variant="destructive">
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
};

/** A success-variant Alert for a confirmation message, or nothing when null. */
export const ConfirmationAlert: React.FC<MessageAlertProps> = ({ message }) => {
  if (!message) return null;
  return (
    <Alert variant="success">
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
};

/** A success-variant Alert for a message, rendering nothing when null. */
export const SuccessAlert: React.FC<MessageAlertProps> = ({ message }) => {
  if (!message) return null;
  return (
    <Alert variant="success">
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
};
