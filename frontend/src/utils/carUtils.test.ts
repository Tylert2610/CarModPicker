import { describe, expect, it } from 'vitest';
import { carFullDisplayName } from './carUtils';
import type { CarGenerationRead } from '../types/Api';

function makeCar(partial: Partial<CarGenerationRead>): CarGenerationRead {
  return {
    id: '00000000-0000-0000-0000-000000000000',
    car_make_name: '',
    car_model_name: '',
    car_model_display_name: null,
    generation_name: '',
    display_name: null,
    start_year: 2020,
    end_year: null,
    description: null,
    image_urls: null,
    display_label: '',
    car_model_display_label: '',
    ...partial,
  };
}

describe('carFullDisplayName', () => {
  it('drops duplicated model when generation display includes it', () => {
    const car = makeCar({
      car_make_name: 'Toyota',
      car_model_name: 'GR86',
      car_model_display_label: 'GR86',
      generation_name: 'ZN8',
      display_name: 'GR86 (ZN8)',
      display_label: 'GR86 (ZN8)',
    });
    expect(carFullDisplayName(car)).toBe('Toyota GR86 (ZN8)');
  });

  it('drops duplicated model when generation display is suffix form', () => {
    const car = makeCar({
      car_make_name: 'Toyota',
      car_model_name: 'Supra',
      car_model_display_label: 'Supra',
      generation_name: 'A80',
      display_name: 'Mk4 Supra',
      display_label: 'Mk4 Supra',
    });
    expect(carFullDisplayName(car)).toBe('Toyota Mk4 Supra');
  });

  it('keeps model when generation display does not mention it', () => {
    const car = makeCar({
      car_make_name: 'BMW',
      car_model_name: '3 Series',
      car_model_display_label: '3 Series',
      generation_name: 'E46',
      display_name: null,
      display_label: 'E46',
    });
    expect(carFullDisplayName(car)).toBe('BMW 3 Series E46');
  });

  it('handles model names with hyphens', () => {
    const car = makeCar({
      car_make_name: 'Mazda',
      car_model_name: 'RX-7',
      car_model_display_label: 'RX-7',
      generation_name: 'FD',
      display_name: '3rd Gen RX-7',
      display_label: '3rd Gen RX-7',
    });
    expect(carFullDisplayName(car)).toBe('Mazda 3rd Gen RX-7');
  });

  it('handles multi-word model names', () => {
    const car = makeCar({
      car_make_name: 'Tesla',
      car_model_name: 'Model 3',
      car_model_display_label: 'Model 3',
      generation_name: 'Highland',
      display_name: 'Model 3 Highland',
      display_label: 'Model 3 Highland',
    });
    expect(carFullDisplayName(car)).toBe('Tesla Model 3 Highland');
  });

  it('does not strip on partial word overlap', () => {
    const car = makeCar({
      car_make_name: 'Toyota',
      car_model_name: '86',
      car_model_display_label: '86',
      generation_name: 'ZN6',
      display_name: null,
      display_label: 'ZN6',
    });
    expect(carFullDisplayName(car)).toBe('Toyota 86 ZN6');
  });
});
