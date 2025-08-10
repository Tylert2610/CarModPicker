import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import HomePage from '../../pages/Home'

// Mock the useAuth hook
const mockUseAuth = vi.fn()
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders welcome message', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
    })

    renderWithRouter(<HomePage />)
    
    expect(screen.getByText('Welcome to CarModPicker!')).toBeInTheDocument()
  })

  it('renders guest content when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
    })

    renderWithRouter(<HomePage />)
    
    expect(screen.getByText(/Your ultimate platform for discovering/)).toBeInTheDocument()
    expect(screen.getByText('Login to Start Your Build')).toBeInTheDocument()
    expect(screen.getByText('Login')).toBeInTheDocument()
    expect(screen.getByText('Register')).toBeInTheDocument()
  })

  it('renders authenticated user content', () => {
    mockUseAuth.mockReturnValue({
      user: { username: 'testuser', id: 1 },
      isAuthenticated: true,
    })

    renderWithRouter(<HomePage />)
    
    expect(screen.getByText('Hello, testuser!')).toBeInTheDocument()
    expect(screen.getByText(/Explore and manage your car modifications/)).toBeInTheDocument()
    expect(screen.getByText('Start Your Build')).toBeInTheDocument()
  })

  it('does not show guest content when authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: { username: 'testuser', id: 1 },
      isAuthenticated: true,
    })

    renderWithRouter(<HomePage />)
    
    expect(screen.queryByText('Login to Start Your Build')).not.toBeInTheDocument()
    expect(screen.queryByText(/Please Login or Register/)).not.toBeInTheDocument()
  })

  it('has correct container classes', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
    })

    renderWithRouter(<HomePage />)
    
    const container = screen.getByText('Welcome to CarModPicker!').parentElement
    expect(container).toHaveClass('container', 'mx-auto', 'p-4', 'text-center')
  })
})
