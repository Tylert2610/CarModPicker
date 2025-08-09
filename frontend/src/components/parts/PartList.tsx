import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { PartRead } from '../../types/Api';

import Card from '../common/Card';
import SectionHeader from '../layout/SectionHeader';
import LoadingSpinner from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/Alerts';
import ActionButton from '../buttons/ActionButton';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';

interface PartListProps {
  buildListId: number;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  title?: string;
  emptyMessage?: string;
}

const fetchPartsRequestFn = (buildListId: number) =>
  apiClient.get<PartRead[]>(`/parts?build_list_id=${buildListId}`);

function PartList({
  buildListId,
  canManageParts,
  refreshKey,
  onAddPartClick,
  title = 'Parts',
  emptyMessage = 'No parts found.',
}: PartListProps) {
  const {
    data: parts,
    isLoading,
    error,
    executeRequest: fetchParts,
  } = useApiRequest(fetchPartsRequestFn);

  useEffect(() => {
    void fetchParts(buildListId);
  }, [buildListId, refreshKey, fetchParts]);

  if (isLoading) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load parts: ${error}`} />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
        {canManageParts && onAddPartClick && (
          <ActionButton onClick={onAddPartClick}>
            Add Part
          </ActionButton>
        )}
      </div>

      {!parts || parts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {parts.map((part) => (
            <Link
              key={part.id}
              to={`/parts/${part.id}`}
              className="block group"
            >
              <div className="bg-gray-800 rounded-lg p-4 hover:bg-gray-700 transition-colors duration-200 border border-gray-700 hover:border-gray-600">
                <div className="aspect-square mb-3">
                  <ImageWithPlaceholder
                    srcUrl={part.image_url}
                    altText={part.name}
                    imageClassName="w-full h-full object-cover rounded"
                    containerClassName="w-full h-full flex justify-center items-center"
                    fallbackText="No image"
                  />
                </div>
                <h3 className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors duration-200 mb-2">
                  {part.name}
                </h3>
                {part.manufacturer && (
                  <p className="text-sm text-gray-400 mb-1">
                    {part.manufacturer}
                  </p>
                )}
                {part.part_number && (
                  <p className="text-sm text-gray-400 mb-1">
                    #{part.part_number}
                  </p>
                )}
                {part.price !== null && part.price !== undefined && (
                  <p className="text-sm font-medium text-green-400">
                    ${part.price.toFixed(2)}
                  </p>
                )}
                {part.description && (
                  <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                    {part.description}
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

export default PartList;
