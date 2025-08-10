import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Card from '../../../components/common/Card'

describe('Card', () => {
  it('renders children correctly', () => {
    render(
      <Card>
        <div data-testid="card-content">Test content</div>
      </Card>
    )
    
    expect(screen.getByTestId('card-content')).toBeInTheDocument()
    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('applies default classes', () => {
    render(<Card>Test</Card>)
    
    const cardElement = screen.getByText('Test').closest('div')
    expect(cardElement).toHaveClass('bg-gray-900', 'shadow-md', 'rounded-lg', 'p-6')
  })

  it('applies custom className', () => {
    render(<Card className="custom-class">Test</Card>)
    
    const cardElement = screen.getByText('Test').closest('div')
    expect(cardElement).toHaveClass('custom-class')
  })

  it('handles onClick events', () => {
    const handleClick = vi.fn()
    render(<Card onClick={handleClick}>Test</Card>)
    
    const cardElement = screen.getByText('Test').closest('div')
    expect(cardElement).not.toBeNull()
    fireEvent.click(cardElement as Element)
    
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('renders without onClick handler', () => {
    render(<Card>Test</Card>)
    
    const cardElement = screen.getByText('Test').closest('div')
    expect(cardElement).not.toBeNull()
    // Should not throw when clicking without onClick handler
    fireEvent.click(cardElement as Element)
    // No error should be thrown, and nothing else should happen
  })
})
