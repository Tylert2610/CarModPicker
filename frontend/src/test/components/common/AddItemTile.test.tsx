import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AddItemTile from '../../../components/common/AddItemTile';

describe('AddItemTile', () => {
  it('renders with title and description', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Add New Item"
        description="Click to add a new item"
        onClick={handleClick}
      />
    );

    expect(screen.getByText('Add New Item')).toBeInTheDocument();
    expect(screen.getByText('Click to add a new item')).toBeInTheDocument();
  });

  it('applies default classes', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Test"
        description="Test description"
        onClick={handleClick}
      />
    );

    const tile = screen.getByText('Test').closest('div');
    expect(tile).toHaveClass(
      'bg-gray-900',
      'shadow-md',
      'rounded-lg',
      'p-6',
      'cursor-pointer',
      'hover:bg-gray-800',
      'flex',
      'flex-col',
      'items-center',
      'justify-center',
      'text-center',
      'h-full',
      'min-h-[200px]',
      'border-2',
      'border-dashed',
      'border-gray-700',
      'hover:border-indigo-500',
      'transition-colors'
    );
  });

  it('applies custom className', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Test"
        description="Test description"
        onClick={handleClick}
        className="custom-class"
      />
    );

    const tile = screen.getByText('Test').closest('div');
    expect(tile).toHaveClass('custom-class');
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Add New Item"
        description="Click to add a new item"
        onClick={handleClick}
      />
    );

    const tile = screen.getByText('Add New Item').closest('div');
    fireEvent.click(tile as Element);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders with proper heading structure', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Add New Item"
        description="Click to add a new item"
        onClick={handleClick}
      />
    );

    const heading = screen.getByRole('heading', { level: 3 });
    expect(heading).toHaveTextContent('Add New Item');
    expect(heading).toHaveClass(
      'text-xl',
      'font-semibold',
      'text-indigo-400',
      'mb-2'
    );
  });

  it('renders description with proper styling', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Add New Item"
        description="Click to add a new item"
        onClick={handleClick}
      />
    );

    const description = screen.getByText('Click to add a new item');
    expect(description).toHaveClass('text-gray-400', 'text-sm');
  });

  it('has proper hover effects', () => {
    const handleClick = vi.fn();
    render(
      <AddItemTile
        title="Add New Item"
        description="Click to add a new item"
        onClick={handleClick}
      />
    );

    const tile = screen.getByText('Add New Item').closest('div');
    expect(tile).toHaveClass(
      'hover:bg-gray-800',
      'hover:border-indigo-500',
      'transition-colors'
    );
  });
});
