import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ActionButton from '../../../components/buttons/ActionButton'

describe('ActionButton', () => {
  it('renders button with children', () => {
    render(<ActionButton>Click me</ActionButton>)
    
    const button = screen.getByRole('button', { name: 'Click me' })
    expect(button).toBeInTheDocument()
  })

  it('applies default classes', () => {
    render(<ActionButton>Test</ActionButton>)
    
    const button = screen.getByRole('button')
    expect(button).toHaveClass(
      'px-4',
      'py-2',
      'bg-indigo-600',
      'hover:bg-indigo-700',
      'text-white',
      'rounded-md',
      'text-sm',
      'font-medium',
      'focus:outline-none',
      'focus:ring-2',
      'focus:ring-offset-2',
      'focus:ring-indigo-500',
      'focus:ring-offset-gray-800'
    )
  })

  it('applies custom className', () => {
    render(<ActionButton className="custom-class">Test</ActionButton>)
    
    const button = screen.getByRole('button')
    expect(button).toHaveClass('custom-class')
  })

  it('handles click events', () => {
    const handleClick = vi.fn()
    render(<ActionButton onClick={handleClick}>Click me</ActionButton>)
    
    const button = screen.getByRole('button')
    fireEvent.click(button)
    
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('passes through additional props', () => {
    render(
      <ActionButton data-testid="custom-button" disabled>
        Test
      </ActionButton>
    )
    
    const button = screen.getByTestId('custom-button')
    expect(button).toBeDisabled()
  })

  it('has correct button type', () => {
    render(<ActionButton>Test</ActionButton>)
    
    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('type', 'button')
  })
})
