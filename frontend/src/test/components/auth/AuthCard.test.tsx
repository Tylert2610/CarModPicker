import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '../../utils/test-utils';
import AuthCard from '../../../components/auth/AuthCard';

describe('AuthCard', () => {
  it('renders with title and children', () => {
    render(
      <AuthCard title="Test Auth">
        <div data-testid="auth-content">Auth content</div>
      </AuthCard>
    );

    expect(screen.getByText('Test Auth')).toBeInTheDocument();
    expect(screen.getByTestId('auth-content')).toBeInTheDocument();
    expect(screen.getByText('Auth content')).toBeInTheDocument();
  });

  it('renders with different title', () => {
    render(
      <AuthCard title="Login">
        <div>Content</div>
      </AuthCard>
    );

    expect(screen.getByText('Login')).toBeInTheDocument();
  });

  it('renders children correctly', () => {
    render(
      <AuthCard title="Test Auth">
        <div data-testid="auth-content">Auth content</div>
        <button>Submit</button>
      </AuthCard>
    );

    expect(screen.getByTestId('auth-content')).toBeInTheDocument();
    expect(screen.getByText('Auth content')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument();
  });

  it('has proper styling classes', () => {
    render(
      <AuthCard title="Test Auth">
        <div>Content</div>
      </AuthCard>
    );

    // Find the container div that has the min-h-screen classes
    const container = screen
      .getByText('Test Auth')
      .closest('div[class*="min-h-screen"]');
    expect(container).toHaveClass(
      'min-h-screen',
      'flex',
      'items-center',
      'justify-center'
    );
  });

  it('has proper card styling', () => {
    render(
      <AuthCard title="Test Auth">
        <div>Content</div>
      </AuthCard>
    );

    // Find the card div that contains the title
    const card = screen
      .getByText('Test Auth')
      .closest('div[class*="max-w-md"]');
    expect(card).toHaveClass(
      'max-w-md',
      'w-full',
      'space-y-8',
      'p-10',
      'bg-gray-950',
      'rounded-xl',
      'shadow-lg'
    );
  });

  it('renders title with proper styling', () => {
    render(
      <AuthCard title="Test Auth">
        <div>Content</div>
      </AuthCard>
    );

    const title = screen.getByText('Test Auth');
    expect(title).toHaveClass(
      'mt-6',
      'text-center',
      'text-3xl',
      'font-extrabold',
      'text-white'
    );
  });
});
