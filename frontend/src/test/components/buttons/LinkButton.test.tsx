import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import LinkButton from '../../../components/buttons/LinkButton'

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

describe('LinkButton', () => {
  it('renders link with children', () => {
    const { getByRole } = renderWithRouter(
      <LinkButton to="/test">Click me</LinkButton>
    )
    
    const link = getByRole('link', { name: 'Click me' })
    expect(link).toBeInTheDocument()
  })

  it('has correct href attribute', () => {
    const { getByRole } = renderWithRouter(
      <LinkButton to="/test">Test</LinkButton>
    )
    
    const link = getByRole('link')
    expect(link).toHaveAttribute('href', '/test')
  })

  it('applies default classes', () => {
    const { getByRole } = renderWithRouter(
      <LinkButton to="/test">Test</LinkButton>
    )
    
    const link = getByRole('link')
    expect(link).toHaveClass(
      'bg-indigo-600',
      'hover:bg-indigo-700',
      'text-white',
      'font-bold',
      'py-3',
      'px-6',
      'rounded-lg',
      'text-lg'
    )
  })

  it('passes through additional props', () => {
    const { getByTestId } = renderWithRouter(
      <LinkButton 
        to="/test" 
        data-testid="custom-link"
        target="_blank"
      >
        Test
      </LinkButton>
    )
    
    const link = getByTestId('custom-link')
    expect(link).toHaveAttribute('target', '_blank')
  })
})
