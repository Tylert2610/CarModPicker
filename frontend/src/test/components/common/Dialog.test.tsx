import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Dialog from '../../../components/common/Dialog'

describe('Dialog', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    title: 'Test Dialog',
    children: <div>Dialog content</div>,
  }

  it('renders when open', () => {
    render(<Dialog {...defaultProps} />)
    
    expect(screen.getByText('Test Dialog')).toBeInTheDocument()
    expect(screen.getByText('Dialog content')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    render(<Dialog {...defaultProps} isOpen={false} />)
    
    expect(screen.queryByText('Test Dialog')).not.toBeInTheDocument()
    expect(screen.queryByText('Dialog content')).not.toBeInTheDocument()
  })

  it('renders with correct title', () => {
    render(<Dialog {...defaultProps} />)
    
    const title = screen.getByRole('heading', { level: 2 })
    expect(title).toHaveTextContent('Test Dialog')
    expect(title).toHaveClass('text-xl', 'font-semibold', 'text-white')
  })

  it('renders close button', () => {
    render(<Dialog {...defaultProps} />)
    
    const closeButton = screen.getByRole('button', { name: 'Close dialog' })
    expect(closeButton).toBeInTheDocument()
    expect(closeButton).toHaveTextContent('×')
  })

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn()
    render(<Dialog {...defaultProps} onClose={onClose} />)
    
    const closeButton = screen.getByRole('button', { name: 'Close dialog' })
    fireEvent.click(closeButton)
    
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders with correct container classes', () => {
    render(<Dialog {...defaultProps} />)
    
    const overlay = document.querySelector('.fixed.inset-0.bg-black\\/50')
    expect(overlay).toBeInTheDocument()
  })

  it('renders with correct dialog classes', () => {
    render(<Dialog {...defaultProps} />)
    
    const dialog = document.querySelector('.bg-gray-900.p-6.rounded-lg.shadow-xl')
    expect(dialog).toBeInTheDocument()
  })

  it('renders children correctly', () => {
    const customChildren = <div data-testid="custom-content">Custom content</div>
    render(<Dialog {...defaultProps} children={customChildren} />)
    
    expect(screen.getByTestId('custom-content')).toBeInTheDocument()
    expect(screen.getByText('Custom content')).toBeInTheDocument()
  })
})
