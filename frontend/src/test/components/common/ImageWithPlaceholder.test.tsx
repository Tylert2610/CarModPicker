import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ImageWithPlaceholder from '../../../components/common/ImageWithPlaceholder'

describe('ImageWithPlaceholder', () => {
  it('renders image when srcUrl is provided', () => {
    render(
      <ImageWithPlaceholder 
        srcUrl="https://example.com/image.jpg" 
        altText="Test image" 
      />
    )
    
    const image = screen.getByRole('img', { name: 'Test image' })
    expect(image).toBeInTheDocument()
    expect(image).toHaveAttribute('src', 'https://example.com/image.jpg')
  })

  it('renders fallback text when srcUrl is not provided', () => {
    render(<ImageWithPlaceholder altText="Test image" />)
    
    expect(screen.getByText('No image set')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('renders custom fallback text', () => {
    render(
      <ImageWithPlaceholder 
        altText="Test image" 
        fallbackText="Custom fallback" 
      />
    )
    
    expect(screen.getByText('Custom fallback')).toBeInTheDocument()
  })

  it('renders fallback text when srcUrl is null', () => {
    render(
      <ImageWithPlaceholder 
        srcUrl={null} 
        altText="Test image" 
      />
    )
    
    expect(screen.getByText('No image set')).toBeInTheDocument()
  })

  it('applies custom image classes', () => {
    render(
      <ImageWithPlaceholder 
        srcUrl="https://example.com/image.jpg" 
        altText="Test image" 
        imageClassName="custom-image-class"
      />
    )
    
    const image = screen.getByRole('img')
    expect(image).toHaveClass('custom-image-class')
  })

  it('applies custom container classes', () => {
    render(
      <ImageWithPlaceholder 
        srcUrl="https://example.com/image.jpg" 
        altText="Test image" 
        containerClassName="custom-container-class"
      />
    )
    
    const container = screen.getByRole('img').parentElement
    expect(container).toHaveClass('custom-container-class')
  })

  it('applies custom fallback text classes', () => {
    render(
      <ImageWithPlaceholder 
        altText="Test image" 
        fallbackTextClassName="custom-fallback-class"
      />
    )
    
    const fallbackText = screen.getByText('No image set')
    expect(fallbackText).toHaveClass('custom-fallback-class')
  })

  it('renders fallback with correct container classes', () => {
    render(<ImageWithPlaceholder altText="Test image" />)
    
    const fallbackContainer = screen.getByText('No image set').parentElement
    expect(fallbackContainer).toHaveClass('flex', 'items-center', 'justify-center', 'border', 'border-gray-400', 'p-2')
  })

  it('handles image load error', () => {
    render(
      <ImageWithPlaceholder 
        srcUrl="https://example.com/image.jpg" 
        altText="Test image" 
      />
    )
    
    const image = screen.getByRole('img')
    fireEvent.error(image)
    
    // After error, should show fallback text
    expect(screen.getByText('No image set')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
