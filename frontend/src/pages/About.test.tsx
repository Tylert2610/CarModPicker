import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import About from './About';

describe('About page', () => {
  it('renders the About CarModPicker heading', () => {
    render(<About />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /about carmodpicker/i })
    ).toBeInTheDocument();
  });

  it('renders key content sections (mission, features, values)', () => {
    render(<About />, testScenarios.unauthenticated);
    const headings = screen.getAllByRole('heading');
    expect(headings.length).toBeGreaterThan(1);
    expect(
      screen.getByRole('heading', { name: /our mission/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /our values/i })
    ).toBeInTheDocument();
  });
});
