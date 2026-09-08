import { useCallback, useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi } from '../../api/build_lists';
import type {
  BuildListRead,
  BuildListReadWithVotes,
  PaginatedResponse,
} from '../../types/Api';

import { ErrorAlert } from '../ui/alert';
import { Card } from '../ui/card';
import Spinner from '../ui/spinner';
import SectionHeader from '../layout/SectionHeader';
import BuildListCard from './BuildListCard';
import BuildListItem from './BuildListItem';

interface BuildListCatalogListProps {
  params?: {
    skip?: number;
    limit?: number;
    search?: string;
    min_cost_cents?: number;
    max_cost_cents?: number;
    sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
  };
  carIds?: string[]; // Optional: filter by car IDs
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  /** When 'card', renders build cards with image previews (Home-style). Default 'list'. */
  layout?: 'card' | 'list';
}

const fetchBuildListsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  search?: string;
  car_id?: string;
  car_ids?: string[];
  min_cost_cents?: number;
  max_cost_cents?: number;
  sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
}) => buildListsApi.getBuildListsWithVotes(params);

// Type predicate to check if response is a PaginatedResponse
function isPaginatedResponse<T>(
  response: unknown
): response is PaginatedResponse<T> {
  return (
    typeof response === 'object' &&
    response !== null &&
    'data' in response &&
    Array.isArray(response.data) &&
    'pagination' in response
  );
}

function BuildListCatalogList({
  params,
  carIds,
  refreshKey = 0,
  title = 'Build Lists Catalog',
  emptyMessage = 'No build lists found.',
  showVoteButtons = false,
  layout = 'list',
}: BuildListCatalogListProps) {
  const [buildListsWithVotes, setBuildListsWithVotes] = useState<
    BuildListReadWithVotes[]
  >([]);

  // Use standard fetch when no carIds are provided
  const {
    data: buildListsResponse,
    isLoading,
    error,
    executeRequest: fetchBuildLists,
  } = useApiRequest<
    PaginatedResponse<BuildListReadWithVotes>,
    {
      skip?: number;
      limit?: number;
      search?: string;
      car_id?: string;
      car_ids?: string[];
      min_cost_cents?: number;
      max_cost_cents?: number;
      sort?: 'votes' | 'votes_asc' | 'price_asc' | 'price_desc';
    }
  >(fetchBuildListsRequestFn);

  // Update buildListsWithVotes when response changes
  useEffect(() => {
    if (isPaginatedResponse<BuildListReadWithVotes>(buildListsResponse)) {
      // Extract the array from PaginatedResponse

      setBuildListsWithVotes(buildListsResponse.data);
    } else if (buildListsResponse === null) {
      // If response is null, clear the votes list
      setBuildListsWithVotes([]);
    }
  }, [buildListsResponse]);

  const handleVoteUpdate = useCallback(
    (buildListId: string, newVote: 'upvote' | 'downvote' | null) => {
      // Update local state optimistically
      setBuildListsWithVotes((prev) =>
        prev.map((bl) => {
          if (bl.id === buildListId) {
            let newUpvotes = bl.upvotes;
            let newDownvotes = bl.downvotes;

            // Remove previous vote
            if (bl.user_vote === 'upvote') {
              newUpvotes -= 1;
            } else if (bl.user_vote === 'downvote') {
              newDownvotes -= 1;
            }

            // Add new vote
            if (newVote === 'upvote') {
              newUpvotes += 1;
            } else if (newVote === 'downvote') {
              newDownvotes += 1;
            }

            return {
              ...bl,
              upvotes: newUpvotes,
              downvotes: newDownvotes,
              total_votes: newUpvotes + newDownvotes,
              user_vote: newVote,
            };
          }
          return bl;
        })
      );
    },
    []
  );

  // Stable request key so we only refetch when the actual request changes (avoids duplicate fetches from parent re-renders)
  const fetchRequestKey = `${refreshKey}-${carIds?.join(',') ?? ''}-${params?.skip ?? 0}-${params?.limit ?? 0}-${params?.sort ?? ''}-${params?.search ?? ''}-${params?.min_cost_cents ?? ''}-${params?.max_cost_cents ?? ''}`;

  useEffect(() => {
    if (carIds && carIds.length > 0) {
      void fetchBuildLists({
        ...params,
        car_ids: carIds,
      });
    } else {
      void fetchBuildLists(params);
    }
  }, [fetchRequestKey]); // eslint-disable-line react-hooks/exhaustive-deps -- intentionally only refetch when request key changes; fetchBuildLists/params/carIds are used inside

  // Filter build lists by search term if provided
  // When carIds is set we use the with-votes endpoint with car_ids - data is in buildListsWithVotes
  let filteredBuildLists: (BuildListRead | BuildListReadWithVotes)[] = [];
  if (carIds && carIds.length > 0) {
    filteredBuildLists = buildListsWithVotes;
  } else {
    // No carIds - use buildListsResponse
    if (showVoteButtons) {
      filteredBuildLists = buildListsWithVotes;
    } else {
      // Extract the array from PaginatedResponse
      if (isPaginatedResponse<BuildListReadWithVotes>(buildListsResponse)) {
        filteredBuildLists = buildListsResponse.data;
      } else {
        filteredBuildLists = [];
      }
    }
  }
  const searchTerm = params?.search?.toLowerCase() || '';
  const finalBuildLists = searchTerm
    ? filteredBuildLists.filter(
        (bl) =>
          bl.name?.toLowerCase().includes(searchTerm) ||
          bl.description?.toLowerCase().includes(searchTerm)
      )
    : filteredBuildLists;

  const isLoadingState = isLoading;
  const errorState = error;

  if (isLoadingState) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      </Card>
    );
  }

  if (errorState) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load build lists: ${errorState}`} />
      </Card>
    );
  }

  if (layout === 'card') {
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
        </div>
        {finalBuildLists.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>{emptyMessage}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {finalBuildLists.map((buildList) => (
              <BuildListCard key={buildList.id} buildList={buildList} />
            ))}
          </div>
        )}
      </>
    );
  }

  return (
    <Card>
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
      </div>

      {finalBuildLists.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="tile-grid-compact">
          {finalBuildLists.map((buildList) => {
            const props: {
              buildList: BuildListRead | BuildListReadWithVotes;
              showVoteButtons: boolean;
              onVoteUpdate?: (
                buildListId: string,
                newVote: 'upvote' | 'downvote' | null
              ) => void;
            } = {
              buildList,
              showVoteButtons,
            };
            if (showVoteButtons) {
              props.onVoteUpdate = handleVoteUpdate;
            }
            return <BuildListItem key={buildList.id} {...props} />;
          })}
        </div>
      )}
    </Card>
  );
}

export default BuildListCatalogList;
