import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { buildListPartsApi, partsApi, categoriesApi } from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  BuildListPartRead,
  PartRead,
  CategoryResponse,
} from '../../types/Api';

import Card from '../common/Card';
import SectionHeader from '../layout/SectionHeader';
import LoadingSpinner from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/Alerts';
import ActionButton from '../buttons/ActionButton';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import VoteButtons from './VoteButtons';

interface BuildListPartsProps {
  buildListId: number;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListPartsRequestFn = (buildListId: number) =>
  buildListPartsApi.getPartsInBuildList(buildListId);

function BuildListParts({
  buildListId,
  canManageParts,
  refreshKey,
  onAddPartClick,
  title = 'Parts',
  emptyMessage = 'No parts found.',
}: BuildListPartsProps) {
  const [parts, setParts] = useState<PartRead[]>([]);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const {
    data: buildListParts,
    isLoading: isLoadingBuildListParts,
    error: buildListPartsError,
    executeRequest: fetchBuildListParts,
  } = useApiRequest(fetchBuildListPartsRequestFn);

  useEffect(() => {
    void fetchBuildListParts(buildListId);
    void loadCategories();
  }, [buildListId, refreshKey, fetchBuildListParts]);

  useEffect(() => {
    if (buildListParts) {
      loadPartsDetails();
    }
  }, [buildListParts]);

  const loadCategories = async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  const loadPartsDetails = async () => {
    if (!buildListParts) return;

    try {
      setLoading(true);
      const partIds = buildListParts.map((bp) => bp.part_id);
      const partsData: PartRead[] = [];

      // Fetch each part's details
      for (const partId of partIds) {
        try {
          const response = await partsApi.getPart(partId);
          partsData.push(response.data);
        } catch (error) {
          console.error(`Failed to load part ${partId}:`, error);
        }
      }

      setParts(partsData);
    } catch (error) {
      console.error('Failed to load parts details:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleVoteUpdate = (
    partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => {
    // Update the part's vote data in the local state
    // This is a simplified implementation - in a real app you might want to refetch the data
    console.log(`Vote updated for part ${partId}: ${newVote}`);
  };

  const handleRemovePart = async (partId: number) => {
    try {
      await buildListPartsApi.removePartFromBuildList(buildListId, partId);
      // Refresh the parts list
      void fetchBuildListParts(buildListId);
    } catch (error) {
      console.error('Failed to remove part from build list:', error);
    }
  };

  if (isLoadingBuildListParts || loading) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      </Card>
    );
  }

  if (buildListPartsError) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load parts: ${buildListPartsError}`} />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
        {canManageParts && onAddPartClick && (
          <ActionButton onClick={onAddPartClick}>Add Part</ActionButton>
        )}
      </div>

      {!parts || parts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {parts.map((part) => {
            const buildListPart = buildListParts?.find(
              (bp) => bp.part_id === part.id
            );
            const category = categories.find((c) => c.id === part.category_id);

            return (
              <div
                key={part.id}
                className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors duration-200"
              >
                <Link to={`/parts/${part.id}`} className="block group">
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
                </Link>

                {part.brand && (
                  <p className="text-sm text-gray-400 mb-1">{part.brand}</p>
                )}

                {part.part_number && (
                  <p className="text-sm text-gray-400 mb-1">
                    #{part.part_number}
                  </p>
                )}

                {category && (
                  <p className="text-sm text-blue-400 mb-1">
                    {category.display_name}
                  </p>
                )}

                {part.price !== null && part.price !== undefined && (
                  <p className="text-sm font-medium text-green-400 mb-2">
                    ${part.price.toLocaleString()}
                  </p>
                )}

                {part.description && (
                  <p className="text-sm text-gray-400 mb-3 line-clamp-2">
                    {part.description}
                  </p>
                )}

                {/* Voting Section */}
                <div className="mb-3">
                  <VoteButtons
                    partId={part.id}
                    upvotes={0} // These would need to be fetched separately
                    downvotes={0}
                    userVote={null}
                    onVoteUpdate={handleVoteUpdate}
                    size="sm"
                  />
                </div>

                {/* Build List Notes */}
                {buildListPart?.notes && (
                  <div className="mb-3 p-2 bg-gray-700 rounded text-sm">
                    <p className="text-gray-300 font-medium mb-1">Notes:</p>
                    <p className="text-gray-400">{buildListPart.notes}</p>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex justify-between items-center">
                  <Link
                    to={`/parts/${part.id}`}
                    className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                  >
                    View Details
                  </Link>

                  {canManageParts && (
                    <button
                      onClick={() => handleRemovePart(part.id)}
                      className="text-red-400 hover:text-red-300 text-sm font-medium"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export default BuildListParts;
