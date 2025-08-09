import React, { useState, useEffect, useCallback, useMemo } from 'react'; 
import type { PartRead } from '../../types/Api';
import PartListItem from './PartListItem';
import SectionHeader from '../layout/SectionHeader';
import { ErrorAlert } from '../common/Alerts';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import LoadingSpinner from '../common/LoadingSpinner';
import AddItemTile from '../common/AddItemTile';

interface PartListProps {
  buildListId: number;
  canManageParts: boolean; // To determine if current user can add/edit/delete parts
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddPartClick?: () => void; // Callback to open create form
}

const PartList: React.FC<PartListProps> = ({
  buildListId,
  canManageParts,
  refreshKey,
  title = 'Parts',
  emptyMessage = 'No parts found for this build list.',
  onAddPartClick,
}) => {
  const [internalParts, setInternalParts] = useState<PartRead[] | null>(null);

  const fetchPartsByBuildListIdRequestFn = useCallback(
    (id: number) => apiClient.get<PartRead[]>(`/parts/build-list/${id}`),
    []
  );

  const {
    data: fetchedApiParts,
    isLoading,
    error,
    executeRequest: fetchBuildListParts,
  } = useApiRequest(fetchPartsByBuildListIdRequestFn);

  useEffect(() => {
    fetchBuildListParts(buildListId);
  }, [buildListId, fetchBuildListParts, refreshKey]);

  useEffect(() => {
    if (fetchedApiParts) {
      setInternalParts(fetchedApiParts);
    } else if (!isLoading && !error) {
      setInternalParts([]);
    }
  }, [fetchedApiParts, isLoading, error]);

  const totalPrice = useMemo(() => {
    if (!internalParts) return 0;
    return internalParts.reduce((sum, part) => sum + (part.price || 0), 0);
  }, [internalParts]);

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
        <ErrorAlert message={`Failed to load parts: ${error}`} />
      </>
    );
  }

  const noPartsToShow = !internalParts || internalParts.length === 0;

  return (
    <div>
      <div className="flex justify-between items-center mb-4"> {/* Container for header and total */}
        <SectionHeader title={title} />
        {internalParts && internalParts.length > 0 && (
          <div className="text-right">
            <span className="text-sm text-gray-400">Total Est. Price:</span>
            <p className="text-xl font-bold text-indigo-400">${totalPrice.toFixed(2)}</p>
          </div>
        )}
      </div>
      <div className="flex flex-col gap-4"> 
        {canManageParts && onAddPartClick && (
          <AddItemTile
            title="Add New Part"
            description="Click here to add a part to this build list."
            onClick={onAddPartClick}
          />
        )}
        {internalParts &&
          internalParts.map((part) => (
            <PartListItem key={part.id} part={part} />
          ))}
      </div>
      {noPartsToShow && !canManageParts && (
        <p className="text-gray-400 mt-4">{emptyMessage}</p>
      )}
      {noPartsToShow && canManageParts && (
        <p className="text-gray-400 mt-4">
          This build list has no parts yet. Click the tile above to add one!
        </p>
      )}
    </div>
  );
};

export default PartList;
