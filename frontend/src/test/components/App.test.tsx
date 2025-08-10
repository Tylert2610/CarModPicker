import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '../../contexts/AuthContext'
import App from '../../App'

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  )
}

describe('App', () => {
  it('renders without crashing', () => {
    // This test now includes the necessary providers
    expect(() => renderWithProviders(<App />)).not.toThrow()
  })
})
