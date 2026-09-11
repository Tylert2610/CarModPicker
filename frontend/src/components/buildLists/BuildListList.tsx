import React, { useCallback, useEffect, useState } from 'react';
import {
  BUILDER_FIRST_PAGE_BUILD_LISTS,
  BUILDER_ITEMS_PER_PAGE,
  BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS,
} from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi } from '../../api/build_lists';
import AddItemTile from './AddItemTile';
import { ErrorAlert } from '../ui/alert';
import Pagination from '../ui/pagination';
import Spinner from '../ui/spinner';
import SectionHeader from '../layout/SectionHeader';
import BuildListItem from './BuildListItem';

interface BuildListListProps {
  carId: string;
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  onAddBuildListClick?: () => void;
  search?: string | undefined;
}

/** Renders a collection of build lists, with an empty state. */
const BuildListList: React.FC<BuildListListProps> = ({
  carId,
  refreshKey,
  title = 'Build Lists',
  emptyMessage = 'No build lists found for this car.',
  onAddBuildListClick,
  search,
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState<number | null>(null);
  const itemsPerPage = BUILDER_ITEMS_PER_PAGE;
  const isFirstPage = currentPage === 1;
  const buildListsPerPage = isFirstPage
    ? BUILDER_FIRST_PAGE_BUILD_LISTS
    : BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS;

  const fetchBuildListsByCarIdRequestFn = useCallback(() => {
    const skip = isFirstPage
      ? 0
      : BUILDER_FIRST_PAGE_BUILD_LISTS +
        (currentPage - 2) * BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS;
    return buildListsApi.getBuildListsByCar(carId, {
      skip,
      limit: buildListsPerPage,
      ...(search && { search }),
    });
  }, [carId, currentPage, isFirstPage, buildListsPerPage, search]);

  const {
    data: buildListsResponse,
    isLoading,
    error,
    executeRequest: fetchCarBuildLists,
  } = useApiRequest(fetchBuildListsByCarIdRequestFn);

  const buildLists = buildListsResponse?.data || [];
  const totalBuildLists = buildListsResponse?.pagination?.total_items ?? 0;

  useEffect(() => {
    if (buildListsResponse) {
      setTotalItems(totalBuildLists + 1);
    }
  }, [buildListsResponse, totalBuildLists]);

  useEffect(() => {
    void fetchCarBuildLists();
  }, [fetchCarBuildLists, refreshKey]);

  useEffect(() => {
    setCurrentPage(1);
    setTotalItems(null);
  }, [refreshKey, search]);

  const canAddBuildList = onAddBuildListClick !== undefined;

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

  const noBuildListsToShow = buildLists.length === 0;

  return (
    <div>
      <SectionHeader title={title} />
      <div className="tile-grid-compact mt-4">
        {canAddBuildList && isFirstPage && (
          <AddItemTile
            title="Create New Build List"
            description="Click here to start a new build list for this car."
            onClick={onAddBuildListClick}
          />
        )}
        {buildLists.length > 0 ? (
          buildLists.map((buildList) => (
            <BuildListItem key={buildList.id} buildList={buildList} />
          ))
        ) : isFirstPage && canAddBuildList ? (
          <div className="col-span-full text-center py-8 text-gray-400">
            <p className="mb-4">
              This car has no build lists yet. Click the tile above to create
              one!
            </p>
          </div>
        ) : null}
      </div>
      {noBuildListsToShow && !canAddBuildList && (
        <p className="text-gray-400 mt-4">{emptyMessage}</p>
      )}
      {totalItems !== null && totalItems > itemsPerPage && (
        <Pagination
          currentPage={currentPage}
          totalPages={Math.ceil(totalItems / itemsPerPage)}
          onPageChange={(page) => {
            setCurrentPage(page);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          itemsPerPage={itemsPerPage}
          totalItems={totalItems}
        />
      )}
    </div>
  );
};

export default BuildListList;
