import { useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { globalPartsApi } from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { GlobalPartReadWithVotes } from '../../types/Api';

import Card from '../common/Card';
import SectionHeader from '../layout/SectionHeader';
import LoadingSpinner from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/Alerts';
import ActionButton from '../buttons/ActionButton';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import VoteButtons from './VoteButtons';

interface GlobalPartListProps {
  params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  };
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  onVoteUpdate?: (
    partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => void;
  onAddToBuildList?: (globalPart: GlobalPartReadWithVotes) => void;
  showAddToBuildListButton?: boolean;
}

const fetchGlobalPartsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  category_id?: number;
  search?: string;
}) => globalPartsApi.getGlobalPartsWithVotes(params);

function GlobalPartList({
  params,
  refreshKey = 0,
  title = 'Global Parts Catalog',
  emptyMessage = 'No global parts found.',
  showVoteButtons = false,
  onVoteUpdate,
  onAddToBuildList,
  showAddToBuildListButton = false,
}: GlobalPartListProps) {
  const {
    data: globalParts,
    isLoading,
    error,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  const memoizedFetchGlobalParts = useCallback(() => {
    void fetchGlobalParts(params);
  }, [fetchGlobalParts, params]);

  useEffect(() => {
    memoizedFetchGlobalParts();
  }, [memoizedFetchGlobalParts, refreshKey]);

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
        <ErrorAlert message={`Failed to load global parts: ${error}`} />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
      </div>

      {!globalParts || globalParts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {globalParts.map((globalPart) => (
            <div
              key={globalPart.id}
              className="bg-gray-800 rounded-lg p-4 border border-gray-700"
            >
              <Link
                to={`/global-parts/${globalPart.id}`}
                className="block group"
              >
                <div className="aspect-square mb-3">
                  <ImageWithPlaceholder
                    srcUrl={globalPart.image_url}
                    altText={globalPart.name}
                    imageClassName="w-full h-full object-cover rounded"
                    containerClassName="w-full h-full flex justify-center items-center"
                    fallbackText="No image"
                  />
                </div>
                <h3 className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors duration-200 mb-2">
                  {globalPart.name}
                </h3>
                {globalPart.brand && (
                  <p className="text-sm text-gray-400 mb-1">
                    {globalPart.brand}
                  </p>
                )}
                {globalPart.part_number && (
                  <p className="text-sm text-gray-400 mb-1">
                    #{globalPart.part_number}
                  </p>
                )}
                {globalPart.price !== null &&
                  globalPart.price !== undefined && (
                    <p className="text-sm font-medium text-green-400">
                      ${globalPart.price.toFixed(2)}
                    </p>
                  )}
                {globalPart.description && (
                  <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                    {globalPart.description}
                  </p>
                )}
              </Link>

              {/* Vote Buttons */}
              {showVoteButtons && onVoteUpdate && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <VoteButtons
                    partId={globalPart.id}
                    upvotes={globalPart.upvotes}
                    downvotes={globalPart.downvotes}
                    userVote={globalPart.user_vote}
                    onVoteUpdate={onVoteUpdate}
                  />
                </div>
              )}

              {/* Add to Build List Button */}
              {showAddToBuildListButton && onAddToBuildList && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <ActionButton
                    onClick={() => onAddToBuildList(globalPart)}
                    className="w-full"
                  >
                    📋 Add to Build List
                  </ActionButton>
                  <p className="text-xs text-gray-500 mt-1 text-center">
                    Creates a personal copy
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default GlobalPartList;
