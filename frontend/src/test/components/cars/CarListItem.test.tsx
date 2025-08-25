import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render, createMockCar } from '../../utils/test-utils';
import CarListItem from '../../../components/cars/CarListItem';

describe('CarListItem', () => {
  const mockCar = createMockCar();

  beforeEach(() => {
    // Clear any previous renders
    document.body.innerHTML = '';
  });

  it('renders car information correctly', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      expect(screen.getByText('2020 Toyota Camry')).toBeInTheDocument();
      expect(screen.getByText('SE')).toBeInTheDocument();
    });
  });

  it('displays car image when available', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      const image = screen.getByAltText('2020 Toyota Camry');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', 'https://example.com/car.jpg');
      expect(image).toHaveClass(
        'w-full',
        'h-40',
        'object-cover',
        'rounded-md',
        'mb-4'
      );
    });
  });

  it('does not display image when not available', async () => {
    const carWithoutImage = createMockCar({ image_url: null });
    render(<CarListItem car={carWithoutImage} />);

    await waitFor(() => {
      expect(
        screen.queryByAltText('2020 Toyota Camry')
      ).not.toBeInTheDocument();
    });
  });

  it('displays VIN when available', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      expect(screen.getByText('1HGBH41JXMN109186')).toBeInTheDocument();
    });
  });

  it('handles car without VIN', async () => {
    const carWithoutVin = createMockCar({ vin: null });
    render(<CarListItem car={carWithoutVin} />);

    await waitFor(() => {
      expect(screen.getByText('2020 Toyota Camry')).toBeInTheDocument();
      expect(screen.queryByText('1HGBH41JXMN109186')).not.toBeInTheDocument();
    });
  });

  it('handles car without trim', async () => {
    const carWithoutTrim = createMockCar({ trim: null });
    render(<CarListItem car={carWithoutTrim} />);

    await waitFor(() => {
      expect(screen.getByText('2020 Toyota Camry')).toBeInTheDocument();
      expect(screen.queryByText('SE')).not.toBeInTheDocument();
    });
  });

  it('has proper link to car detail page', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/cars/1');
      expect(link).toHaveClass('block', 'hover:no-underline', 'h-full');
    });
  });

  it('has proper card styling classes', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      // Find the Card component (the div with Card styling)
      const card = screen
        .getByText('2020 Toyota Camry')
        .closest('div[class*="bg-gray-900"]');
      expect(card).toHaveClass('bg-gray-900', 'shadow-md', 'rounded-lg', 'p-6');
    });
  });

  it('displays car ID in card info', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      expect(screen.getByText('Car ID')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  it('has proper hover effects on card', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      const card = screen
        .getByText('2020 Toyota Camry')
        .closest('div[class*="bg-gray-900"]');
      expect(card).toHaveClass(
        'hover:border-indigo-500',
        'border-2',
        'border-transparent',
        'transition-colors'
      );
    });
  });

  it('renders with proper text styling', async () => {
    render(<CarListItem car={mockCar} />);

    await waitFor(() => {
      const title = screen.getByText('2020 Toyota Camry');
      expect(title).toHaveClass(
        'text-lg',
        'font-semibold',
        'text-indigo-400',
        'mb-2'
      );
    });
  });

  it('handles car with all optional fields', async () => {
    const completeCar = createMockCar({
      trim: 'XSE',
      vin: '5YJSA1E47HF123456',
      image_url: 'https://example.com/complete-car.jpg',
    });

    render(<CarListItem car={completeCar} />);

    await waitFor(() => {
      expect(screen.getByText('2020 Toyota Camry')).toBeInTheDocument();
      expect(screen.getByText('XSE')).toBeInTheDocument();
      expect(screen.getByText('5YJSA1E47HF123456')).toBeInTheDocument();
      expect(screen.getByAltText('2020 Toyota Camry')).toHaveAttribute(
        'src',
        'https://example.com/complete-car.jpg'
      );
    });
  });

  it('handles car with minimal data', async () => {
    const minimalCar = createMockCar({
      trim: null,
      vin: null,
      image_url: null,
    });

    render(<CarListItem car={minimalCar} />);

    await waitFor(() => {
      expect(screen.getByText('2020 Toyota Camry')).toBeInTheDocument();
      expect(screen.getByText('Car ID')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.queryByText('SE')).not.toBeInTheDocument();
      expect(screen.queryByText('1HGBH41JXMN109186')).not.toBeInTheDocument();
      expect(
        screen.queryByAltText('2020 Toyota Camry')
      ).not.toBeInTheDocument();
    });
  });
});
