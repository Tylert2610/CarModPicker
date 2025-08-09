import React, { useState, useEffect, useCallback } from 'react';
import type { CarRead } from '../../types/Api';
import CarListItem from './CarListItem';
import SectionHeader from '../layout/SectionHeader';
import { ErrorAlert } from '../common/Alerts';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import LoadingSpinner from '../common/LoadingSpinner';
import AddItemTile from '../common/AddItemTile';

interface CarListProps {
  userId?: number;
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddCarClick?: () => void;
  showAddCarTile?: boolean;
}

const CarList: React.FC<CarListProps> = ({
  userId,
  refreshKey,
  title = 'Cars',
  emptyMessage = 'No cars found.',
  onAddCarClick,
  showAddCarTile = false,
}) => {
  const [internalCars, setInternalCars] = useState<CarRead[] | null>(null);

  const fetchCarsByUserIdRequestFn = useCallback(
    (id: number) => apiClient.get<CarRead[]>(`/cars/user/${id}`),
    []
  );

  const {
    data: fetchedApiCars,
    isLoading,
    error,
    executeRequest: fetchUserCars,
  } = useApiRequest(fetchCarsByUserIdRequestFn);

  useEffect(() => {
    if (userId) {
      fetchUserCars(userId);
    } else {
      setInternalCars([]);
    }
  }, [userId, fetchUserCars, refreshKey]); // Depend on userId, fetchUserCars, and refreshKey

  useEffect(() => {
    if (fetchedApiCars) {
      setInternalCars(fetchedApiCars);
    } else if (!isLoading && userId && !error) {
      setInternalCars([]);
    }
  }, [fetchedApiCars, isLoading, userId, error]);

  if (isLoading) {
    return (
      <>
        <SectionHeader title={title} />
        <LoadingSpinner />
      </>
    );
  }

  if (userId && error) {
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
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 mt-4">
        {showAddCarTile && onAddCarClick && (
          <AddItemTile
            title="Add a New Car"
            description="Click here to add a vehicle to your garage."
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
          You have no cars yet. Click the tile above to add your first one!
        </p>
      )}
    </div>
  );
};

export default CarList;
