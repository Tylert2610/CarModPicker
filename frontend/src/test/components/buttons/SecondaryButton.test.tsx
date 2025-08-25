import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { render } from '../../utils/test-utils';
import SecondaryButton from '../../../components/buttons/SecondaryButton';

describe('SecondaryButton', () => {
  it('renders with children text', () => {
    render(<SecondaryButton>Click me</SecondaryButton>);

    expect(
      screen.getByRole('button', { name: 'Click me' })
    ).toBeInTheDocument();
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(<SecondaryButton onClick={handleClick}>Click me</SecondaryButton>);

    const button = screen.getByRole('button', { name: 'Click me' });
    fireEvent.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('applies custom className', () => {
    render(
      <SecondaryButton className="custom-class">Click me</SecondaryButton>
    );

    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toHaveClass('custom-class');
  });

  it('can be disabled', () => {
    render(<SecondaryButton disabled>Click me</SecondaryButton>);

    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toBeDisabled();
  });

  it('has default styling classes', () => {
    render(<SecondaryButton>Click me</SecondaryButton>);

    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toHaveClass(
      'py-2',
      'px-4',
      'border',
      'border-gray-600',
      'rounded-md'
    );
  });

  it('applies custom className correctly', () => {
    render(
      <SecondaryButton className="custom-class">Click me</SecondaryButton>
    );

    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toHaveClass('custom-class');
  });

  it('forwards additional props', () => {
    render(
      <SecondaryButton data-testid="custom-button">Click me</SecondaryButton>
    );

    const button = screen.getByTestId('custom-button');
    expect(button).toBeInTheDocument();
  });
});
