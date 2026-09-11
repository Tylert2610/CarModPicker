import * as React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ConfirmDialog } from './confirm-dialog';

function renderControlled(
  initialProps: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}
) {
  const onConfirm = vi.fn();
  const onOpenChange = vi.fn();
  const utils = render(
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
      title="Delete build list"
      description="This action cannot be undone."
      confirmLabel="Delete"
      {...initialProps}
    />
  );
  return { onConfirm, onOpenChange, ...utils };
}

describe('ConfirmDialog', () => {
  it('does not render dialog content when open=false', () => {
    render(
      <ConfirmDialog
        open={false}
        onOpenChange={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete build list"
      />
    );
    expect(screen.queryByTestId('confirm-dialog')).toBeNull();
  });

  it('renders title, description, and default labels when open', () => {
    renderControlled({ confirmLabel: 'Confirm', cancelLabel: 'Cancel' });
    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
    expect(screen.getByText('Delete build list')).toBeInTheDocument();
    expect(
      screen.getByText('This action cannot be undone.')
    ).toBeInTheDocument();
    expect(screen.getByTestId('confirm-dialog-confirm')).toHaveTextContent(
      'Confirm'
    );
    expect(screen.getByTestId('confirm-dialog-cancel')).toHaveTextContent(
      'Cancel'
    );
  });

  it('fires onConfirm when the confirm button is clicked', () => {
    const { onConfirm, onOpenChange } = renderControlled();
    fireEvent.click(screen.getByTestId('confirm-dialog-confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it('fires onOpenChange(false) when cancel button is clicked', () => {
    const { onOpenChange, onConfirm } = renderControlled();
    fireEvent.click(screen.getByTestId('confirm-dialog-cancel'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('disables both buttons while loading and surfaces aria-busy on confirm', () => {
    renderControlled({ loading: true, loadingLabel: 'Deleting...' });
    const confirm = screen.getByTestId('confirm-dialog-confirm');
    const cancel = screen.getByTestId('confirm-dialog-cancel');
    expect(confirm).toBeDisabled();
    expect(cancel).toBeDisabled();
    expect(confirm).toHaveAttribute('aria-busy', 'true');
    expect(confirm).toHaveTextContent('Deleting...');
  });

  it('does not auto-close on confirm click while loading (parent controls open state)', () => {
    const { onOpenChange, onConfirm } = renderControlled({ loading: true });
    const confirm = screen.getByTestId('confirm-dialog-confirm');
    fireEvent.click(confirm);
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('cancel click is a no-op while loading', () => {
    const { onOpenChange } = renderControlled({ loading: true });
    fireEvent.click(screen.getByTestId('confirm-dialog-cancel'));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it('renders the inline error region when error is provided', () => {
    renderControlled({ error: 'Server exploded' });
    const errorEl = screen.getByTestId('confirm-dialog-error');
    expect(errorEl).toBeInTheDocument();
    expect(errorEl).toHaveTextContent('Server exploded');
    expect(errorEl).toHaveAttribute('role', 'alert');
  });

  it('does not render the error region when error is null/undefined', () => {
    renderControlled({ error: null });
    expect(screen.queryByTestId('confirm-dialog-error')).toBeNull();
  });

  it('renders the warning slot when provided', () => {
    renderControlled({
      warning: <span>This part is currently in 3 build lists</span>,
    });
    const warningEl = screen.getByTestId('confirm-dialog-warning');
    expect(warningEl).toBeInTheDocument();
    expect(warningEl).toHaveTextContent(
      'This part is currently in 3 build lists'
    );
  });

  it('does not render the warning slot when omitted', () => {
    renderControlled();
    expect(screen.queryByTestId('confirm-dialog-warning')).toBeNull();
  });

  it('applies destructive button styling when variant=destructive', () => {
    renderControlled({ variant: 'destructive', confirmLabel: 'Delete' });
    const confirm = screen.getByTestId('confirm-dialog-confirm');
    expect(confirm.className).toContain('bg-destructive');
  });

  it('applies default (primary) button styling when variant=default', () => {
    renderControlled({ variant: 'default', confirmLabel: 'Save' });
    const confirm = screen.getByTestId('confirm-dialog-confirm');
    expect(confirm.className).toContain('bg-primary');
    expect(confirm.className).not.toContain('bg-destructive');
  });

  it('renders custom children content between description and footer', () => {
    renderControlled({
      children: <p data-testid="custom-body">Extra context for the user.</p>,
    });
    const body = screen.getByTestId('custom-body');
    expect(body).toBeInTheDocument();
    expect(body).toHaveTextContent('Extra context for the user.');
  });
});
