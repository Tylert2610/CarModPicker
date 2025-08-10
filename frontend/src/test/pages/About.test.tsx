import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import About from '../../pages/About'

describe('About', () => {
  it('renders about page content', () => {
    render(<About />)
    
    expect(screen.getByText('About CarModPicker')).toBeInTheDocument()
    expect(screen.getByText(/CarModPicker is your ultimate platform/)).toBeInTheDocument()
    expect(screen.getByText(/Whether you're a car enthusiast/)).toBeInTheDocument()
  })

  it('renders with correct heading', () => {
    render(<About />)
    
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('About CarModPicker')
    expect(heading).toHaveClass('text-4xl', 'font-bold', 'mb-6')
  })

  it('renders with correct container classes', () => {
    render(<About />)
    
    const container = screen.getByText('About CarModPicker').parentElement
    expect(container).toHaveClass('container', 'mx-auto', 'p-4', 'text-center')
  })

  it('renders loading spinner', () => {
    render(<About />)
    
    // The LoadingSpinner component should be present
    const spinnerContainer = document.querySelector('.flex.justify-center.items-center.p-4')
    expect(spinnerContainer).toBeInTheDocument()
  })

  it('renders paragraphs with correct classes', () => {
    render(<About />)
    
    // Get the specific paragraph elements by their text content
    const paragraph1 = screen.getByText(/CarModPicker is your ultimate platform/)
    const paragraph2 = screen.getByText(/Whether you're a car enthusiast/)
    
    expect(paragraph1).toHaveClass('text-lg', 'mb-4')
    expect(paragraph2).toHaveClass('text-lg', 'mb-4')
  })
})
