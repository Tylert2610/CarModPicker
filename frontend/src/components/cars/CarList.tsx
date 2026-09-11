import React, { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { carGenerationsApi } from '../../api/car_generations';
import type { CarGenerationRead } from '../../types/Api';
import { normalizeCarReadList } from '../../utils/carUtils';
import AddItemTile from '../buildLists/AddItemTile';
import { ErrorAlert } from '../ui/alert';
import Spinner from '../ui/spinner';
import SectionHeader from '../layout/SectionHeader';
import CarListItem from './CarListItem';

interface CarListProps {
  searchQuery?: string;
  make?: string;
  year?: number;
  generationId?: string;
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddCarClick?: () => void;
  showAddCarTile?: boolean;
  limit?: number;
  skip?: number;
}

/** Renders a collection of cars, with an empty state. */
const CarList: React.FC<CarListProps> = ({
  searchQuery,
  make,
  year,
  generationId,
  refreshKey,
  title = 'Cars',
  emptyMessage = 'No cars found.',
  onAddCarClick,
  showAddCarTile = false,
  limit = 100,
  skip = 0,
}) => {
  const [internalCars, setInternalCars] = useState<CarGenerationRead[] | null>(
    null
  );

  const fetchCarsRequestFn = useCallback(
    async (payload?: unknown) => {
      void payload;
      let response: Awaited<ReturnType<typeof carGenerationsApi.listCars>>;
      if (searchQuery) {
        response = await carGenerationsApi.searchCars(searchQuery, {
          skip,
          limit,
        });
      } else if (generationId) {
        const single = await carGenerationsApi.getCar(generationId);
        return { ...single, data: [single.data] };
      } else if (make && year) {
        response = await carGenerationsApi.searchCars(`${make} ${year}`, {
          skip,
          limit,
        });
      } else if (make) {
        response = await carGenerationsApi.getCarsByMake(make, { skip, limit });
      } else if (year) {
        response = await carGenerationsApi.searchCars(String(year), {
          skip,
          limit,
        });
      } else {
        response = await carGenerationsApi.listCars({ skip, limit });
      }
      return response;
    },
    [searchQuery, make, year, generationId, skip, limit]
  );

  const {
    data: fetchedApiCars,
    isLoading,
    error,
    executeRequest: fetchCars,
  } = useApiRequest<CarGenerationRead[]>(fetchCarsRequestFn);

  useEffect(() => {
    void fetchCars();
  }, [fetchCars, refreshKey]);

  useEffect(() => {
    if (fetchedApiCars != null) {
      setInternalCars(normalizeCarReadList(fetchedApiCars));
    } else if (!isLoading && !error) {
      setInternalCars([]);
    }
  }, [fetchedApiCars, isLoading, error]);

  if (isLoading) {
    return (
      <>
        <SectionHeader title={title} />
        <Spinner />
      </>
    );
  }

  if (error) {
    return (
      <>
        <SectionHeader title={title} />
        <ErrorAlert message={error} />
      </>
    );
  }

  const noCarsToShow = !internalCars || internalCars.length === 0;

  return (
    <div>
      <SectionHeader title={title} />
      <div className="tile-grid-compact mt-4">
        {showAddCarTile && onAddCarClick && (
          <AddItemTile
            title="Add a New Car"
            description="Click here to add a vehicle (Admin only)."
            onClick={onAddCarClick}
          />
        )}
        {internalCars &&
          internalCars.map((car) => <CarListItem key={car.id} car={car} />)}
      </div>
      {noCarsToShow && !showAddCarTile && (
        <p className="text-gray-400 mt-4">{emptyMessage}</p>
      )}
      {noCarsToShow && showAddCarTile && (
        <p className="text-gray-400 mt-4">
          No cars found. Click the tile above to add one (Admin only)!
        </p>
      )}
    </div>
  );
};

export default CarList;
