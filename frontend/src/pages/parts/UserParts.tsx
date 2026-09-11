import React, { useCallback, useState } from 'react';
import PartList from '../../components/parts/PartList';
import PartsFilterSidebar from '../../components/parts/PartsFilterSidebar';
import PartsActiveFilterChips from '../../components/parts/PartsActiveFilterChips';
import PageHeader from '../../components/layout/PageHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Card } from '../../components/ui/card';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { Input } from '../../components/ui/input';
import Pagination from '../../components/ui/pagination';
import { useAuth } from '../../hooks/useAuth';
import { usePartsFilters } from '../../hooks/usePartsFilters';
import { buildListPartsApi } from '../../api/build_list_parts';
import { partsApi } from '../../api/parts';
import type { PartReadWithVotes, PaginationInfo } from '../../types/Api';

/** The signed in user's own parts, with deletion. */
const UserParts: React.FC = () => {
  const { user, isAuthenticated } = useAuth();

  const [deletingPartId, setDeletingPartId] = useState<string | null>(null);
  const [deletingPartName, setDeletingPartName] = useState<string>('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);
  const [listRefreshKey, setListRefreshKey] = useState(0);

  const filterOptions: Parameters<typeof usePartsFilters>[0] = {
    syncToUrl: false,
  };
  if (user?.id !== undefined) filterOptions.user_id = user.id;
  const filters = usePartsFilters(filterOptions);

  const handlePaginationChange = useCallback(
    (pagination: PaginationInfo | null) => {
      filters.setPaginationInfo(pagination);
    },
    [filters]
  );

  const handleDeleteClick = useCallback((part: PartReadWithVotes) => {
    setDeletingPartId(part.id);
    setDeletingPartName(part.name);
    void (async () => {
      try {
        const response = await buildListPartsApi.countBuildListsContainingPart(
          part.id
        );
        setBuildListCount(response.data.count);
      } catch {
        setBuildListCount(null);
      }
    })();
  }, []);

  const handleDelete = useCallback(async () => {
    if (!deletingPartId) return;
    setIsDeleting(true);
    try {
      await partsApi.deletePart(deletingPartId);
      setDeletingPartId(null);
      setDeletingPartName('');
      setBuildListCount(null);
      filters.setCurrentPage(1);
      setListRefreshKey((k) => k + 1);
    } catch {
      // Failed
    } finally {
      setIsDeleting(false);
    }
  }, [deletingPartId, filters]);

  const canDelete = useCallback(
    (part: PartReadWithVotes) =>
      !!user &&
      (part.user_id === user.id || user.is_admin || user.is_superuser),
    [user]
  );

  const sidebarProps = {
    hasActiveFilters: filters.hasActiveFilters,
    clearAllFilters: filters.clearAllFilters,
    showUniversalParts: filters.showUniversalParts,
    setShowUniversalParts: filters.setShowUniversalParts,
    selectedMake: filters.selectedMake,
    selectedModel: filters.selectedModel,
    selectedGeneration: filters.selectedGeneration,
    setSelectedMake: filters.setSelectedMake,
    setSelectedModel: filters.setSelectedModel,
    setSelectedGeneration: filters.setSelectedGeneration,
    availableMakes: filters.availableMakes,
    uniqueModels: filters.uniqueModels,
    generations: filters.generations,
    isLoadingMakes: filters.isLoadingMakes,
    isLoadingCars: filters.isLoadingCars,
    priceMin: filters.priceMin,
    priceMax: filters.priceMax,
    setPriceMin: filters.setPriceMin,
    setPriceMax: filters.setPriceMax,
    activeCategories: filters.activeCategories,
    availableCategoryIds: filters.availableCategoryIds,
    selectedCategoryIds: filters.selectedCategoryIds,
    toggleCategory: filters.toggleCategory,
    setSelectedCategoryIds: filters.setSelectedCategoryIds,
    availablePartManufacturers: filters.availablePartManufacturers,
    availablePartManufacturerIds: filters.availablePartManufacturerIds,
    selectedPartManufacturerIds: filters.selectedPartManufacturerIds,
    togglePartManufacturer: filters.togglePartManufacturer,
    setSelectedPartManufacturerIds: filters.setSelectedPartManufacturerIds,
  };

  const chipsProps = {
    hasActiveFilters: filters.hasActiveFilters,
    selectedCategoryIds: filters.selectedCategoryIds,
    activeCategories: filters.activeCategories,
    toggleCategory: filters.toggleCategory,
    selectedPartManufacturerIds: filters.selectedPartManufacturerIds,
    availablePartManufacturers: filters.availablePartManufacturers,
    togglePartManufacturer: filters.togglePartManufacturer,
    selectedGeneration: filters.selectedGeneration,
    showUniversalParts: filters.showUniversalParts,
    clearVehicleFilter: filters.clearVehicleFilter,
    hasPriceRange: filters.hasPriceRange,
    priceMin: filters.priceMin,
    priceMax: filters.priceMax,
    clearPriceRange: filters.clearPriceRange,
  };

  if (!isAuthenticated || !user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <ErrorAlert message="You must be logged in to view your parts." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="My Parts" />
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <PartsFilterSidebar {...sidebarProps} />

        <main className="flex-1 min-w-0">
          <div className="mb-4">
            <Input
              type="text"
              placeholder="Search your parts..."
              value={filters.searchTerm}
              onChange={(e) => filters.setSearchTerm(e.target.value)}
              className="w-full max-w-md"
            />
          </div>

          <PartsActiveFilterChips {...chipsProps} />

          <PartList
            params={filters.params}
            refreshKey={listRefreshKey}
            title=""
            emptyMessage="You haven't created any parts yet. Parts you create will appear here."
            showVoteButtons
            onVoteUpdate={() => {}}
            onDelete={handleDeleteClick}
            canDelete={canDelete}
            onPaginationChange={handlePaginationChange}
            sortParam={filters.sortParam}
            onSortChange={filters.setSortParam}
            layout="table"
            categories={filters.activeCategories}
            part_manufacturers={filters.availablePartManufacturers}
          />

          {filters.paginationInfo && filters.paginationInfo.total_pages > 1 && (
            <Pagination
              currentPage={filters.paginationInfo.current_page}
              totalPages={filters.paginationInfo.total_pages}
              totalItems={filters.paginationInfo.total_items}
              itemsPerPage={filters.paginationInfo.items_per_page}
              onPageChange={filters.setCurrentPage}
            />
          )}
        </main>
      </div>

      <ConfirmDialog
        open={deletingPartId !== null}
        onOpenChange={(open) => {
          if (!open && isDeleting) return;
          if (!open) {
            setDeletingPartId(null);
            setDeletingPartName('');
            setBuildListCount(null);
          }
        }}
        onConfirm={() => void handleDelete()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the part{' '}
            <span className="font-semibold text-foreground">
              &quot;{deletingPartName}&quot;
            </span>
            ? This action cannot be undone.
          </>
        }
        warning={
          buildListCount !== null && buildListCount > 0 ? (
            <>
              <p className="font-semibold mb-1">
                ⚠️ Warning: This part is currently in {buildListCount} build
                list{buildListCount !== 1 ? 's' : ''}
              </p>
              <p className="text-xs">
                Deleting this part will remove it from all {buildListCount}{' '}
                build list{buildListCount !== 1 ? 's' : ''}. This action cannot
                be undone.
              </p>
            </>
          ) : undefined
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isDeleting}
      />
    </div>
  );
};

export default UserParts;
