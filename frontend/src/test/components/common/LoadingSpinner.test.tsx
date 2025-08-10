import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import LoadingSpinner from '../../../components/common/LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders loading spinner', () => {
    render(<LoadingSpinner />)
    
    const spinnerContainer = document.querySelector('.flex.justify-center.items-center.p-4')
    expect(spinnerContainer).toBeInTheDocument()
  })

  it('has correct container classes', () => {
    render(<LoadingSpinner />)
    
    const container = document.querySelector('.flex.justify-center.items-center.p-4')
    expect(container).toHaveClass('flex', 'justify-center', 'items-center', 'p-4')
  })

  it('has correct spinner classes', () => {
    render(<LoadingSpinner />)
    
    const spinner = document.querySelector('.animate-spin')
    expect(spinner).toHaveClass(
      'animate-spin',
      'rounded-full',
      'h-12',
      'w-12',
      'border-t-2',
      'border-b-2',
      'border-indigo-500'
    )
  })

  it('renders with proper structure', () => {
    render(<LoadingSpinner />)
    
    const container = document.querySelector('.flex.justify-center.items-center.p-4')
    const spinner = document.querySelector('.animate-spin')
    
    expect(container).toBeInTheDocument()
    expect(spinner).toBeInTheDocument()
  })
})
