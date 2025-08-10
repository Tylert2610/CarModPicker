import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import Input from '../../../components/common/Input'

describe('Input', () => {
  it('renders input with label', () => {
    const { getByLabelText, getByRole } = render(<Input label="Test Label" id="test-input" />)
    
    expect(getByLabelText('Test Label')).toBeInTheDocument()
    expect(getByRole('textbox')).toBeInTheDocument()
  })

  it('associates label with input correctly', () => {
    const { getByRole, getByText } = render(<Input label="Test Label" id="test-input" />)
    
    const input = getByRole('textbox')
    const label = getByText('Test Label')
    
    expect(input).toHaveAttribute('id', 'test-input')
    expect(label).toHaveAttribute('for', 'test-input')
  })

  it('applies default classes to input', () => {
    const { getByRole } = render(<Input label="Test Label" id="test-input" />)
    
    const input = getByRole('textbox')
    expect(input).toHaveClass(
      'mt-1',
      'block',
      'w-full',
      'px-3',
      'py-2',
      'bg-gray-700',
      'border',
      'border-gray-600',
      'rounded-md',
      'shadow-sm',
      'placeholder-gray-400',
      'focus:outline-none',
      'focus:ring-indigo-500',
      'focus:border-indigo-500',
      'sm:text-sm',
      'text-white'
    )
  })

  it('applies default classes to label', () => {
    const { getByText } = render(<Input label="Test Label" id="test-input" />)
    
    const label = getByText('Test Label')
    expect(label).toHaveClass('block', 'text-sm', 'font-medium', 'text-gray-300')
  })

  it('handles input changes', () => {
    const handleChange = vi.fn()
    const { getByRole } = render(
      <Input 
        label="Test Label" 
        id="test-input" 
        onChange={handleChange}
      />
    )
    
    const input = getByRole('textbox')
    fireEvent.change(input, { target: { value: 'test value' } })
    
    expect(handleChange).toHaveBeenCalledTimes(1)
    expect(input).toHaveValue('test value')
  })

  it('passes through additional props', () => {
    const { getByTestId } = render(
      <Input 
        label="Test Label" 
        id="test-input" 
        placeholder="Enter text"
        required
        data-testid="custom-input"
      />
    )
    
    const input = getByTestId('custom-input')
    expect(input).toHaveAttribute('placeholder', 'Enter text')
    expect(input).toBeRequired()
  })

  it('renders with container classes', () => {
    const { getByRole } = render(<Input label="Test Label" id="test-input" />)
    
    const container = getByRole('textbox').parentElement
    expect(container).toHaveClass('mb-4')
  })
})
