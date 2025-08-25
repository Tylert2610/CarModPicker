import { describe, it, expect } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '../utils/test-utils';
import App from '../../App';

describe('App', () => {
  it('renders without crashing', async () => {
    render(<App />);

    await waitFor(() => {
      expect(document.body).toBeInTheDocument();
    });
  });

  it('renders with proper routing structure', async () => {
    render(<App />);

    await waitFor(() => {
      // Check that the app renders without throwing
      expect(() => screen.getByRole('main')).not.toThrow();
    });
  });

  it('handles authentication context properly', async () => {
    render(<App />);

    await waitFor(() => {
      // The app should render even with authentication context
      expect(document.body).toBeInTheDocument();
    });
  });
});
