import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import ContactUs from '../../pages/ContactUs'

describe('ContactUs', () => {
  it('renders contact page content', () => {
    const { getByText } = render(<ContactUs />)
    
    expect(getByText('Contact Us')).toBeInTheDocument()
    expect(getByText('If you have any questions, feel free to reach out!')).toBeInTheDocument()
  })

  it('renders with correct heading', () => {
    const { getByRole } = render(<ContactUs />)
    
    const heading = getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Contact Us')
  })

  it('renders with proper structure', () => {
    const { container } = render(<ContactUs />)
    
    const mainDiv = container.querySelector('div')
    expect(mainDiv).toBeInTheDocument()
    expect(mainDiv?.children).toHaveLength(2) // h1 and p
  })
})
