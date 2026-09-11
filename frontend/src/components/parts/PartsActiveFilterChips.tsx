import React from 'react';
import { filterChipClass } from '../filters/VehicleFilterChips';
import { Button } from '../ui/button';
import type {
  PartManufacturerResponse,
  CarGenerationRead,
  CategoryResponse,
} from '../../types/Api';
import { carFullDisplayName } from '../../utils/carUtils';

/**
 * Props for PartsActiveFilterChips: the active part filters and how to clear them.
 */
export interface PartsActiveFilterChipsProps {
  hasActiveFilters: boolean;
  selectedCategoryIds: string[];
  activeCategories: CategoryResponse[];
  toggleCategory: (id: string) => void;
  selectedPartManufacturerIds: string[];
  availablePartManufacturers: PartManufacturerResponse[];
  togglePartManufacturer: (id: string) => void;
  selectedGeneration: CarGenerationRead | null;
  selectedMake?: string;
  selectedModel?: string;
  showUniversalParts: boolean;
  clearVehicleFilter: () => void;
  hasPriceRange: boolean;
  priceMin: string;
  priceMax: string;
  clearPriceRange: () => void;
}

/** The active part filters as removable chips. */
const PartsActiveFilterChips: React.FC<PartsActiveFilterChipsProps> = (
  props
) => {
  const {
    hasActiveFilters,
    selectedCategoryIds,
    activeCategories,
    toggleCategory,
    selectedPartManufacturerIds,
    availablePartManufacturers,
    togglePartManufacturer,
    selectedGeneration,
    selectedMake = '',
    selectedModel = '',
    showUniversalParts,
    clearVehicleFilter,
    hasPriceRange,
    priceMin,
    priceMax,
    clearPriceRange,
  } = props;

  if (!hasActiveFilters) return null;

  const removeButtonClass =
    'h-5 w-5 p-0 rounded-full hover:bg-gray-600/80 hover:text-white shrink-0';

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {selectedCategoryIds.map((id) => {
        const cat = activeCategories.find((c) => c.id === id);
        if (!cat) return null;
        return (
          <span key={`cat-${id}`} className={filterChipClass}>
            {cat.display_name || cat.name}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => toggleCategory(id)}
              className={removeButtonClass}
              aria-label="Remove category filter"
            >
              ×
            </Button>
          </span>
        );
      })}
      {selectedPartManufacturerIds.map((id) => {
        const part_manufacturer = availablePartManufacturers.find(
          (b) => b.id === id
        );
        if (!part_manufacturer) return null;
        return (
          <span key={`part_manufacturer-${id}`} className={filterChipClass}>
            {part_manufacturer.name}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => togglePartManufacturer(id)}
              className={removeButtonClass}
              aria-label="Remove part manufacturer filter"
            >
              ×
            </Button>
          </span>
        );
      })}
      {(selectedGeneration || showUniversalParts || selectedMake) && (
        <span className={filterChipClass}>
          {showUniversalParts
            ? 'Universal'
            : selectedGeneration
              ? carFullDisplayName(selectedGeneration).trim()
              : `${selectedMake}${selectedModel ? ` ${selectedModel}` : ''}`.trim() ||
                'Vehicle'}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={clearVehicleFilter}
            className={removeButtonClass}
            aria-label="Remove vehicle filter"
          >
            ×
          </Button>
        </span>
      )}
      {hasPriceRange && (
        <span className={filterChipClass}>
          {priceMin.trim() && priceMax.trim()
            ? `$${priceMin.trim()} – $${priceMax.trim()}`
            : priceMin.trim()
              ? `Min $${priceMin.trim()}`
              : `Max $${priceMax.trim()}`}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={clearPriceRange}
            className={removeButtonClass}
            aria-label="Remove price range filter"
          >
            ×
          </Button>
        </span>
      )}
    </div>
  );
};

export default PartsActiveFilterChips;
