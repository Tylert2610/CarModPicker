import { useCallback, useEffect, useState } from 'react';
import AddItemTile from '../../components/buildLists/AddItemTile';
import BuildListCard from '../../components/buildLists/BuildListCard';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import Pagination from '../../components/ui/pagination';
import Spinner from '../../components/ui/spinner';
import {
  BUILDER_FIRST_PAGE_BUILD_LISTS,
  BUILDER_ITEMS_PER_PAGE,
  BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS,
} from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListsApi } from '../../api/build_lists';
import type { BuildListRead } from '../../types/Api';

function Builder() {
  const { user } = useAuth();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isCreateBuildListFormOpen, setIsCreateBuildListFormOpen] =
    useState(false);
  const [formKey, setFormKey] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = BUILDER_ITEMS_PER_PAGE;
  const [totalItems, setTotalItems] = useState<number | null>(null);
  const isFirstPage = currentPage === 1;
  // On first page: create button (1) + 7 build lists = 8 items
  // On other pages: 8 build lists = 8 items
  const buildListsPerPage = isFirstPage
    ? BUILDER_FIRST_PAGE_BUILD_LISTS
    : BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS;

  // Fetch user's build lists (with vote + total-cost enrichment) with pagination
  const fetchMyBuildListsFn = useCallback(() => {
    if (!user) return Promise.reject(new Error('Not authenticated'));
    // Calculate skip: page 1 = 0, page 2 = 7, page 3 = 15, page 4 = 23, etc.
    const skip = isFirstPage
      ? 0
      : BUILDER_FIRST_PAGE_BUILD_LISTS +
        (currentPage - 2) * BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS;
    return buildListsApi.getBuildListsWithVotes({
      skip,
      limit: buildListsPerPage,
      owner_id: user.id,
    });
  }, [currentPage, isFirstPage, buildListsPerPage, user]);

  const {
    data: buildListsResponse,
    isLoading,
    error,
    executeRequest: fetchMyBuildLists,
  } = useApiRequest(fetchMyBuildListsFn);

  // Extract build lists and total from paginated response
  const buildLists = buildListsResponse?.data || [];
  const totalBuildLists = buildListsResponse?.pagination?.total_items ?? 0;

  // Calculate total items: build lists + 1 for the create button on page 1
  useEffect(() => {
    if (buildListsResponse) {
      // Total items = total build lists + 1 (for the create button on page 1)
      setTotalItems(totalBuildLists + 1);
    }
  }, [buildListsResponse, totalBuildLists]);

  useEffect(() => {
    if (user) {
      void fetchMyBuildLists();
    }
  }, [user, fetchMyBuildLists, refreshTrigger, currentPage]);

  const handleBuildListCreated = (newBuildList: BuildListRead) => {
    // Refresh the list after creation and reset to first page
    void newBuildList;
    setCurrentPage(1);
    setTotalItems(null);
    setRefreshTrigger((prev) => prev + 1);
    setIsCreateBuildListFormOpen(false);
  };

  const openCreateBuildListDialog = () => {
    setFormKey((prev) => prev + 1);
    setIsCreateBuildListFormOpen(true);
  };

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader
          title="Builder"
          subtitle="Please log in to view and manage your build lists."
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Builder"
        subtitle="Manage your build lists and create new ones for your projects."
      />

      <Dialog
        open={isCreateBuildListFormOpen}
        onOpenChange={setIsCreateBuildListFormOpen}
      >
        <DialogContent className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Create New Build List</DialogTitle>
          </DialogHeader>
          <CreateBuildListForm
            key={formKey}
            onBuildListCreated={handleBuildListCreated}
          />
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <div className="mt-8">
          <Spinner />
        </div>
      ) : error ? (
        <div className="mt-8">
          <ErrorAlert message={error} />
        </div>
      ) : (
        <div className="mt-8">
          <SectionHeader title="My Build Lists" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mt-4">
            {isFirstPage && (
              <AddItemTile
                title="Create New Build List"
                description="Click here to start a new build list for your project."
                onClick={openCreateBuildListDialog}
              />
            )}
            {buildLists && buildLists.length > 0 ? (
              buildLists.map((buildList) => (
                <BuildListCard key={buildList.id} buildList={buildList} />
              ))
            ) : isFirstPage ? (
              <div className="col-span-full text-center py-8 text-muted-foreground">
                <p className="mb-4">
                  You don't have any build lists yet. Click the tile above to
                  create your first one!
                </p>
              </div>
            ) : null}
          </div>
          {totalItems !== null && totalItems > itemsPerPage && (
            <Pagination
              currentPage={currentPage}
              totalPages={Math.ceil(totalItems / itemsPerPage)}
              onPageChange={(page) => {
                setCurrentPage(page);
                // Scroll to top when page changes
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              itemsPerPage={itemsPerPage}
              totalItems={totalItems}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default Builder;
