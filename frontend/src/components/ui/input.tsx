import * as React from 'react';
import { type VariantProps } from 'class-variance-authority';

import { cn } from '../../lib/utils';
import { inputVariants } from './input-variants';

/** Props for Input: input attributes plus an error flag for styling. */
export interface InputProps
  extends
    React.InputHTMLAttributes<HTMLInputElement>,
    VariantProps<typeof inputVariants> {
  ref?: React.Ref<HTMLInputElement>;
}

/** A single-line text input styled to the app's form conventions. */
export function Input({ className, type, ref, ...props }: InputProps) {
  return (
    <input
      type={type}
      className={cn(inputVariants(), className)}
      ref={ref}
      {...props}
    />
  );
}
