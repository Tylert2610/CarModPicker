import { useCallback, useMemo } from 'react';
import type { CarGenerationRead } from '../../types/Api';
import { carFullDisplayName } from '../../utils/carUtils';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../forms/SearchableSelect';

/** A car's display name with its year range appended. */
function formatCarLabel(car: CarGenerationRead): string {
  return `${carFullDisplayName(car)} (${car.start_year ?? ''}${
    car.end_year ? `-${car.end_year}` : '+'
  })`;
}

interface CarModelMultiSelectProps {
  cars: CarGenerationRead[];
  value: string[];
  onChange: (carIds: string[]) => void;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  isLoading?: boolean;
  emptyMessage?: string;
}

/**
 * Multi-select for car models: shows selected cars as removable chips
 * and a searchable dropdown to add more.
 */
/**
 * Multi-select for car models: selected cars as removable chips plus a searchable dropdown.
 */
function CarModelMultiSelect({
  cars,
  value,
  onChange,
  label = 'Car models (optional)',
  placeholder = 'Type to search for a car model...',
  disabled = false,
  isLoading = false,
  emptyMessage = 'No cars found or all selected.',
}: CarModelMultiSelectProps) {
  const selectedCars = useMemo(
    () => cars.filter((c) => value.includes(c.id)),
    [cars, value]
  );

  const availableOptions: SearchableSelectOption[] = useMemo(
    () =>
      cars
        .filter((c) => !value.includes(c.id))
        .sort((a, b) => {
          if (a.car_make_name !== b.car_make_name)
            return a.car_make_name.localeCompare(b.car_make_name);
          if (a.car_model_name !== b.car_model_name)
            return a.car_model_name.localeCompare(b.car_model_name);
          return a.generation_name.localeCompare(b.generation_name);
        })
        .map((car) => ({
          id: car.id,
          label: formatCarLabel(car),
          value: car.id,
        })),
    [cars, value]
  );

  const filterOptions = useCallback(
    (options: SearchableSelectOption[], searchText: string) => {
      if (!searchText.trim()) return options;
      const lower = searchText.toLowerCase();
      return options.filter((opt) => opt.label.toLowerCase().includes(lower));
    },
    []
  );

  const handleAddCar = useCallback(
    (selectedValue: number | string | null) => {
      if (selectedValue === null || selectedValue === '') return;
      const id = String(selectedValue);
      if (value.includes(id)) return;
      onChange([...value, id]);
    },
    [value, onChange]
  );

  const handleRemoveCar = useCallback(
    (carId: string) => {
      onChange(value.filter((id) => id !== carId));
    },
    [value, onChange]
  );

  return (
    <div className="space-y-2">
      {label && (
        <label className="block text-sm font-medium text-foreground">
          {label}
        </label>
      )}
      {selectedCars.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedCars.map((car) => (
            <span
              key={car.id}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-info/20 border border-info/40 text-sm text-info"
            >
              <span
                className="truncate max-w-[200px]"
                title={formatCarLabel(car)}
              >
                {formatCarLabel(car)}
              </span>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => handleRemoveCar(car.id)}
                  className="flex-shrink-0 p-0.5 rounded hover:bg-info/30 text-info hover:text-white transition-colors"
                  aria-label={`Remove ${formatCarLabel(car)}`}
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      {!disabled && availableOptions.length > 0 && (
        <SearchableSelect
          id="car-model-add"
          value={null}
          onChange={handleAddCar}
          options={availableOptions}
          placeholder={placeholder}
          disabled={isLoading}
          isLoading={isLoading}
          emptyMessage={emptyMessage}
          filterOptions={filterOptions}
        />
      )}
      {!disabled &&
        availableOptions.length === 0 &&
        !isLoading &&
        value.length > 0 && (
          <p className="text-sm text-muted-foreground">
            All available car models are already selected.
          </p>
        )}
    </div>
  );
}

export default CarModelMultiSelect;
