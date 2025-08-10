import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import PageHeader from '../../../components/layout/PageHeader'

describe('PageHeader', () => {
  it('renders title correctly', () => {
    const { getByRole } = render(<PageHeader title="Test Title" />)
    
    const heading = getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Test Title')
    expect(heading).toHaveClass('text-3xl', 'font-bold', 'text-white')
  })

  it('renders subtitle when provided', () => {
    const { getByText } = render(
      <PageHeader title="Test Title" subtitle="Test Subtitle" />
    )
    
    expect(getByText('Test Subtitle')).toBeInTheDocument()
    expect(getByText('Test Subtitle')).toHaveClass('text-lg', 'text-gray-400', 'mt-1')
  })

  it('does not render subtitle when not provided', () => {
    const { queryByText } = render(<PageHeader title="Test Title" />)
    
    expect(queryByText('Test Subtitle')).not.toBeInTheDocument()
  })

  it('renders with correct container classes', () => {
    const { getByRole } = render(<PageHeader title="Test Title" />)
    
    const container = getByRole('heading').parentElement
    expect(container).toHaveClass('mb-6')
  })

  it('renders both title and subtitle with correct structure', () => {
    const { getByRole, getByText } = render(
      <PageHeader title="Test Title" subtitle="Test Subtitle" />
    )
    
    const heading = getByRole('heading', { level: 1 })
    const subtitle = getByText('Test Subtitle')
    
    expect(heading).toBeInTheDocument()
    expect(subtitle).toBeInTheDocument()
    expect(heading.parentElement).toContainElement(subtitle)
  })
})
