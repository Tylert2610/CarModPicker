import React from 'react';
import type { CarGenerationRead } from '../../types/Api';
import { carFullDisplayName } from '../../utils/carUtils';

/**
 * Props for VehicleFilterChips: the active vehicle filters and how to clear them.
 */
export interface VehicleFilterChipsProps {
  selectedGeneration: CarGenerationRead | null;
  selectedMake?: string;
  selectedModel?: string;
  showUniversalParts: boolean;
  clearVehicleFilter: () => void;
  searchTerm?: string;
  onClearSearch?: () => void;
  /** When false, render chips without wrapper (for use alongside other chips in parent flex) */
  wrapInContainer?: boolean;
}

/** Shared chip styles for consistent size across vehicle, search, cost, etc. */
export const filterChipClass =
  'inline-flex items-center gap-1.5 h-8 pl-3 pr-1 rounded-full bg-gray-800 border border-gray-600/80 text-gray-200 text-sm whitespace-nowrap';
const removeButtonClass =
  'p-0.5 rounded-full hover:bg-gray-600/80 hover:text-white transition-colors shrink-0';

/** The chip text for the current vehicle selection, narrowest part first. */
function vehicleChipLabel(
  selectedGeneration: CarGenerationRead | null,
  selectedMake: string,
  selectedModel: string,
  showUniversalParts: boolean
): string {
  if (showUniversalParts) return 'Universal';
  if (selectedGeneration)
    return carFullDisplayName(selectedGeneration).trim() || 'Vehicle';
  if (selectedMake) {
    const makeModel =
      `${selectedMake}${selectedModel ? ` ${selectedModel}` : ''}`.trim();
    return makeModel || 'Vehicle';
  }
  return 'Vehicle';
}

/** The active vehicle filter as a removable chip. */
const VehicleFilterChips: React.FC<VehicleFilterChipsProps> = ({
  selectedGeneration,
  selectedMake = '',
  selectedModel = '',
  showUniversalParts,
  clearVehicleFilter,
  searchTerm = '',
  onClearSearch,
  wrapInContainer = true,
}) => {
  const hasVehicle =
    selectedGeneration !== null ||
    showUniversalParts ||
    (selectedMake !== '' && !showUniversalParts);
  const hasSearch = searchTerm.trim() !== '' && onClearSearch;
  if (!hasVehicle && !hasSearch) return null;

  const chips = (
    <>
      {hasVehicle && (
        <span className={filterChipClass}>
          {vehicleChipLabel(
            selectedGeneration,
            selectedMake,
            selectedModel,
            showUniversalParts
          )}
          <button
            type="button"
            onClick={clearVehicleFilter}
            className={removeButtonClass}
            aria-label="Remove vehicle filter"
          >
            ×
          </button>
        </span>
      )}
      {hasSearch && (
        <span className={filterChipClass}>
          Search: &quot;{searchTerm.trim()}&quot;
          <button
            type="button"
            onClick={onClearSearch}
            className={removeButtonClass}
            aria-label="Clear search"
          >
            ×
          </button>
        </span>
      )}
    </>
  );

  if (wrapInContainer) {
    return <div className="flex flex-wrap gap-2 mb-4">{chips}</div>;
  }
  return chips;
};

export default VehicleFilterChips;
