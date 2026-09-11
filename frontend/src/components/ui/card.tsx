import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '../../lib/utils';

const cardVariants = cva(
  'rounded-lg border border-border bg-card text-card-foreground shadow-sm',
  {
    variants: {
      variant: {
        default: '',
        glass:
          'border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5',
        elevated: 'border-white/20 bg-white/10 shadow-2xl backdrop-blur-xl',
      },
      padding: {
        none: '',
        sm: 'p-4',
        md: 'p-6',
        lg: 'p-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      padding: 'md',
    },
  }
);

/** Props for Card: div attributes plus the card's visual variant. */
export interface CardProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  ref?: React.Ref<HTMLDivElement>;
}

/** A bordered surface that groups related content. */
export function Card({
  className,
  variant,
  padding,
  ref,
  ...props
}: CardProps) {
  return (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, padding }), className)}
      {...props}
    />
  );
}

type DivWithRef = React.HTMLAttributes<HTMLDivElement> & {
  ref?: React.Ref<HTMLDivElement>;
};

/** The top section of a Card, holding its title and description. */
export function CardHeader({ className, ref, ...props }: DivWithRef) {
  return (
    <div
      ref={ref}
      className={cn('flex flex-col space-y-1.5 p-6', className)}
      {...props}
    />
  );
}

/** The heading inside a CardHeader. */
export function CardTitle({ className, ref, ...props }: DivWithRef) {
  return (
    <div
      ref={ref}
      className={cn(
        'text-lg font-semibold leading-none tracking-tight',
        className
      )}
      {...props}
    />
  );
}

/** The supporting text under a CardTitle. */
export function CardDescription({ className, ref, ...props }: DivWithRef) {
  return (
    <div
      ref={ref}
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  );
}

/** The main body section of a Card. */
export function CardContent({ className, ref, ...props }: DivWithRef) {
  return <div ref={ref} className={cn('p-6 pt-0', className)} {...props} />;
}

/** The bottom section of a Card, usually holding actions. */
export function CardFooter({ className, ref, ...props }: DivWithRef) {
  return (
    <div
      ref={ref}
      className={cn('flex items-center p-6 pt-0', className)}
      {...props}
    />
  );
}
