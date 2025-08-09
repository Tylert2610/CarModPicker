import React, { useState, useEffect, useCallback } from 'react';
import type { BuildListRead } from '../../types/Api';
import BuildListItem from './BuildListItem';
import SectionHeader from '../layout/SectionHeader';
import { ErrorAlert } from '../common/Alerts';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import LoadingSpinner from '../common/LoadingSpinner';
import AddItemTile from '../common/AddItemTile'; 
interface BuildListListProps {
  carId: number;
  carOwnerId?: number; // To determine if current user can add build lists
  currentUserId?: number; // Logged-in user's ID
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddBuildListClick?: () => void; // Callback to open create form
}

const BuildListList: React.FC<BuildListListProps> = ({
  carId,
  carOwnerId,
  currentUserId,
  refreshKey,
  title = 'Build Lists',
  emptyMessage = 'No build lists found for this car.',
  onAddBuildListClick,
}) => {
  const [internalBuildLists, setInternalBuildLists] = useState<
    BuildListRead[] | null
  >(null);

  const fetchBuildListsByCarIdRequestFn = useCallback(
    (id: number) => apiClient.get<BuildListRead[]>(`/build-lists/car/${id}`),
    []
  );

  const {
    data: fetchedApiBuildLists,
    isLoading,
    error,
    executeRequest: fetchCarBuildLists,
  } = useApiRequest(fetchBuildListsByCarIdRequestFn);

  useEffect(() => {
    fetchCarBuildLists(carId);
  }, [carId, fetchCarBuildLists, refreshKey]);

  useEffect(() => {
    if (fetchedApiBuildLists) {
      setInternalBuildLists(fetchedApiBuildLists);
    } else if (!isLoading && !error) {
      setInternalBuildLists([]);
    }
  }, [fetchedApiBuildLists, isLoading, error]);

  const canAddBuildList =
    carOwnerId !== undefined &&
    currentUserId !== undefined &&
    carOwnerId === currentUserId &&
    onAddBuildListClick !== undefined;

  if (isLoading) {
    return (
      <>
        <SectionHeader title={title} />
        <LoadingSpinner />
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

  const noBuildListsToShow =
    !internalBuildLists || internalBuildLists.length === 0;

  return (
    <div>
      <SectionHeader title={title} />
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 mt-4">
        {canAddBuildList && (
          <AddItemTile
            title="Create New Build List"
            description="Click here to start a new build list for this car."
            onClick={onAddBuildListClick}
          />
        )}
        {internalBuildLists &&
          internalBuildLists.map((buildList) => (
            <BuildListItem key={buildList.id} buildList={buildList} />
          ))}
      </div>
      {noBuildListsToShow && !canAddBuildList && (
        <p className="text-gray-400 mt-4">{emptyMessage}</p>
      )}
      {noBuildListsToShow && canAddBuildList && (
        <p className="text-gray-400 mt-4">
          This car has no build lists yet. Click the tile above to create one!
        </p>
      )}
    </div>
  );
};

export default BuildListList;
