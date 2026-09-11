import type { CarGenerationRead } from '../types/Api';

/**
 * Format year range for display; handles null end_year (current/ongoing generation).
 */
export function formatCarYearRange(
  startYear: number,
  endYear: number | null | undefined
): string {
  if (endYear == null) return `${startYear}–present`;
  return `${startYear}–${endYear}`;
}

export function normalizeCarRead(
  car: CarGenerationRead | null | undefined
): CarGenerationRead | null {
  if (car == null) return null;
  const generationName = car.generation_name ?? '';
  const modelName = car.car_model_name ?? '';
  return {
    ...car,
    car_make_name: car.car_make_name ?? '',
    car_model_name: modelName,
    generation_name: generationName,
    display_label: car.display_label ?? car.display_name ?? generationName,
    car_model_display_label:
      car.car_model_display_label ?? car.car_model_display_name ?? modelName,
  };
}

/** Consumer-friendly generation label (e.g. "Mk4 Supra" vs raw "A80"). */
export function carGenerationDisplayName(
  car: Pick<
    CarGenerationRead,
    'display_label' | 'display_name' | 'generation_name'
  >
): string {
  return car.display_label || car.display_name || car.generation_name;
}

/** Consumer-friendly model label. */
export function carModelDisplayName(
  car: Pick<
    CarGenerationRead,
    'car_model_display_label' | 'car_model_display_name' | 'car_model_name'
  >
): string {
  return (
    car.car_model_display_label ||
    car.car_model_display_name ||
    car.car_model_name
  );
}

/** "<make> <model> <generation>" using friendly labels where set. */
export function carFullDisplayName(car: CarGenerationRead): string {
  const make = car.car_make_name ?? '';
  const model = carModelDisplayName(car);
  const generation = carGenerationDisplayName(car);
  const parts =
    model && generationContainsModel(generation, model)
      ? [make, generation]
      : [make, model, generation];
  return parts.filter(Boolean).join(' ');
}

function generationContainsModel(generation: string, model: string): boolean {
  if (!generation || !model) return false;
  const escaped = model.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?:^|\\W)${escaped}(?:$|\\W)`, 'i').test(generation);
}

export function normalizeCarReadList(
  cars: CarGenerationRead[] | null | undefined
): CarGenerationRead[] {
  if (cars == null || !Array.isArray(cars)) return [];
  return cars
    .map(normalizeCarRead)
    .filter((c): c is CarGenerationRead => c != null);
}
