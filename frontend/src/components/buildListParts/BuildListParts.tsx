import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { LARGE_FETCH_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListPartsApi } from '../../api/build_list_parts';
import { buildListPhasesApi } from '../../api/build_list_phases';
import { buildListsApi } from '../../api/build_lists';
import { carGenerationsApi } from '../../api/car_generations';
import { categoriesApi } from '../../api/categories';
import { partManufacturersApi } from '../../api/part_manufacturers';
import type {
  BuildListLaborEstimateRead,
  BuildListPartReadWithPart,
  BuildListPartUpdate,
  BuildListPhaseRead,
  CarGenerationRead,
} from '../../types/Api';
import { normalizeCarReadList } from '../../utils/carUtils';
import SectionHeader from '../layout/SectionHeader';
import { ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Tabs, TabsList, TabsTrigger } from '../ui/tabs';
import BuildListPartList from './BuildListPartList';
import EditBuildListPartForm from './EditBuildListPartForm';
import LaborEstimatesSection from './LaborEstimatesSection';

interface BuildListPartsProps {
  buildListId: string;
  buildListCarId?: string | null;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  onPartsChange?: (parts: BuildListPartReadWithPart[]) => void;
  onLaborEstimatesChange?: (items: BuildListLaborEstimateRead[]) => void;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListPartsRequestFn = (buildListId: string) =>
  buildListPartsApi.getBuildListParts(buildListId);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchPartManufacturersRequestFn = () =>
  partManufacturersApi.getPartManufacturers(true);

const fetchCarsRequestFn = () =>
  carGenerationsApi.listCars({ limit: LARGE_FETCH_LIMIT });

const fetchPhasesRequestFn = (buildListId: string) =>
  buildListsApi.getPhases(buildListId);

const BuildListParts: React.FC<BuildListPartsProps> = ({
  buildListId,
  buildListCarId,
  canManageParts,
  refreshKey,
  onAddPartClick,
  onPartsChange,
  onLaborEstimatesChange,
  title = 'Parts in Build List',
  emptyMessage = 'No parts added to this build list yet.',
}) => {
  const { user: currentUser } = useAuth();
  const [editingPart, setEditingPart] =
    useState<BuildListPartReadWithPart | null>(null);
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingPartId, setDeletingPartId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'category' | 'phase' | 'purchased'>(
    'category'
  );
  const [newPhaseName, setNewPhaseName] = useState('');
  const [isAddingPhase, setIsAddingPhase] = useState(false);
  const [editingPhaseId, setEditingPhaseId] = useState<string | null>(null);
  const [editingPhaseName, setEditingPhaseName] = useState('');
  const [deletingPhaseId, setDeletingPhaseId] = useState<string | null>(null);
  const [phaseError, setPhaseError] = useState<string | null>(null);
  const [isManagePhasesOpen, setIsManagePhasesOpen] = useState(false);

  const {
    data: buildListParts,
    isLoading,
    error,
    executeRequest: fetchBuildListParts,
  } = useApiRequest(fetchBuildListPartsRequestFn);

  const {
    data: categories,
    isLoading: isLoadingCategories,
    executeRequest: fetchCategories,
  } = useApiRequest(fetchCategoriesRequestFn);

  const {
    data: part_manufacturersData,
    executeRequest: fetchPartManufacturers,
  } = useApiRequest(fetchPartManufacturersRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);

  const { data: phases, executeRequest: fetchPhases } =
    useApiRequest(fetchPhasesRequestFn);

  const phasesList: BuildListPhaseRead[] = useMemo(
    () => phases ?? [],
    [phases]
  );
  const part_manufacturers = part_manufacturersData ?? [];
  const carsById = useMemo(() => {
    const list = Array.isArray(carsData) ? carsData : [];
    const normalized = normalizeCarReadList(list);
    const map: Record<string, CarGenerationRead> = {};
    for (const car of normalized) {
      map[car.id] = car;
    }
    return map;
  }, [carsData]);

  // Local state for optimistic updates - sync with API data
  const [localBuildListParts, setLocalBuildListParts] = useState<
    BuildListPartReadWithPart[] | null
  >(null);

  // Sync local state with API data when it changes
  useEffect(() => {
    if (buildListParts) {
      setLocalBuildListParts(buildListParts);
    }
  }, [buildListParts]);

  // Notify parent whenever the parts list changes (after fetches and optimistic updates)
  useEffect(() => {
    if (localBuildListParts && onPartsChange) {
      onPartsChange(localBuildListParts);
    }
  }, [localBuildListParts, onPartsChange]);

  useEffect(() => {
    void fetchBuildListParts(buildListId);
    void fetchCategories();
    void fetchPartManufacturers();
    void fetchCars();
    void fetchPhases(buildListId);
  }, [
    buildListId,
    refreshKey,
    fetchBuildListParts,
    fetchCategories,
    fetchPartManufacturers,
    fetchCars,
    fetchPhases,
  ]);

  // Helper function to check if user can edit a specific build list part
  const canEditBuildListPart = (buildListPart: BuildListPartReadWithPart) => {
    if (!currentUser) return false;
    return buildListPart.added_by === currentUser.id;
  };

  // Helper function to check if user can delete a specific build list part
  const canDeleteBuildListPart = (buildListPart: BuildListPartReadWithPart) => {
    if (!currentUser) return false;
    return (
      buildListPart.added_by === currentUser.id ||
      currentUser.is_admin ||
      currentUser.is_superuser
    );
  };

  const handleEdit = (buildListPart: BuildListPartReadWithPart) => {
    if (!canEditBuildListPart(buildListPart)) {
      return;
    }
    setEditingPart(buildListPart);
    setIsEditFormOpen(true);
  };

  const handleEditSubmit = async (
    _buildListPartId: string,
    data: BuildListPartUpdate
  ) => {
    try {
      setIsUpdating(true);
      await buildListPartsApi.updateBuildListPart(
        buildListId,
        editingPart!.part_id,
        data
      );
      // Refresh the build list parts
      await fetchBuildListParts(buildListId);
    } finally {
      // No catch: the caller handles the failure. This block exists only to
      // clear the updating flag on both paths, and a catch that rethrows
      // unchanged does nothing a bare `finally` does not already do.
      setIsUpdating(false);
    }
  };

  const handleDelete = (buildListPartId: string) => {
    // Find the build list part to get the part_id
    const buildListPart = buildListParts?.find(
      (part) => part.id === buildListPartId
    );
    if (!buildListPart) return;

    if (!canDeleteBuildListPart(buildListPart)) {
      return;
    }

    // Open confirmation dialog instead of directly deleting
    setDeleteError(null);
    setDeletingPartId(buildListPartId);
  };

  const handleConfirmDelete = async () => {
    if (deletingPartId === null) return;

    // Find the build list part to get the part_id
    const buildListPart = buildListParts?.find(
      (part) => part.id === deletingPartId
    );
    if (!buildListPart) {
      setDeletingPartId(null);
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await buildListPartsApi.removeBuildListPart(
        buildListId,
        buildListPart.part_id
      );
      await fetchBuildListParts(buildListId);
      setDeletingPartId(null);
    } catch (error: unknown) {
      setDeleteError(
        error instanceof Error
          ? error.message
          : 'Failed to remove part from build list'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeletePartOpenChange = (open: boolean) => {
    if (open) return;
    if (isDeleting) return;
    setDeletingPartId(null);
    setDeleteError(null);
  };

  const handleCloseEditForm = () => {
    setIsEditFormOpen(false);
    setEditingPart(null);
  };

  const handleAddPhase = async () => {
    const name = newPhaseName.trim();
    if (!name) return;
    setPhaseError(null);
    setIsAddingPhase(true);
    try {
      await buildListsApi.createPhase(buildListId, { name });
      setNewPhaseName('');
      void fetchPhases(buildListId);
    } catch (err) {
      setPhaseError(err instanceof Error ? err.message : 'Failed to add phase');
    } finally {
      setIsAddingPhase(false);
    }
  };

  const handleStartEditPhase = (phase: BuildListPhaseRead) => {
    setEditingPhaseId(phase.id);
    setEditingPhaseName(phase.name);
    setPhaseError(null);
  };

  const handleSaveEditPhase = async () => {
    if (editingPhaseId == null) return;
    const name = editingPhaseName.trim();
    if (!name) return;
    setPhaseError(null);
    try {
      await buildListPhasesApi.updatePhase(editingPhaseId, { name });
      setEditingPhaseId(null);
      setEditingPhaseName('');
      void fetchPhases(buildListId);
    } catch (err) {
      setPhaseError(
        err instanceof Error ? err.message : 'Failed to update phase'
      );
    }
  };

  const handleCancelEditPhase = () => {
    setEditingPhaseId(null);
    setEditingPhaseName('');
    setPhaseError(null);
  };

  const handleDeletePhase = async () => {
    if (deletingPhaseId == null) return;
    try {
      await buildListPhasesApi.deletePhase(deletingPhaseId);
      setDeletingPhaseId(null);
      void fetchPhases(buildListId);
      void fetchBuildListParts(buildListId);
    } catch (err) {
      setPhaseError(
        err instanceof Error ? err.message : 'Failed to delete phase'
      );
    }
  };

  const handleDeletePhaseOpenChange = (open: boolean) => {
    if (open) return;
    setDeletingPhaseId(null);
    setPhaseError(null);
  };

  const handleTogglePurchased = useCallback(
    async (buildListPart: BuildListPartReadWithPart) => {
      if (!canManageParts) return;

      const newPurchasedStatus = !buildListPart.purchased;

      // Optimistic update: update local state immediately
      setLocalBuildListParts((prevParts) => {
        if (!prevParts) return prevParts;
        return prevParts.map((part) =>
          part.id === buildListPart.id
            ? { ...part, purchased: newPurchasedStatus }
            : part
        );
      });

      try {
        await buildListPartsApi.updateBuildListPart(
          buildListId,
          buildListPart.part_id,
          { purchased: newPurchasedStatus }
        );
        // Optionally sync with server, but don't refetch to avoid full re-render
        // The optimistic update is already applied
      } catch {
        // Revert optimistic update on error
        setLocalBuildListParts((prevParts) => {
          if (!prevParts) return prevParts;
          return prevParts.map((part) =>
            part.id === buildListPart.id
              ? { ...part, purchased: buildListPart.purchased }
              : part
          );
        });
      }
    },
    [canManageParts, buildListId]
  );

  // Wrapper to match the expected void return type
  const handleTogglePurchasedWrapper = useCallback(
    (part: BuildListPartReadWithPart) => {
      void handleTogglePurchased(part);
    },
    [handleTogglePurchased]
  );

  // Reassign a part to a phase (null = Unassigned). Optimistic, same pattern
  // as handleTogglePurchased: update local state, then PUT, revert on error.
  const handlePhaseChange = useCallback(
    async (
      buildListPart: BuildListPartReadWithPart,
      phaseId: string | null
    ) => {
      if (!canManageParts) return;
      if ((buildListPart.build_list_phase_id ?? null) === phaseId) return;

      const prevPhaseId = buildListPart.build_list_phase_id ?? null;
      const prevPhaseName = buildListPart.phase_name ?? null;
      const nextPhaseName =
        phaseId == null
          ? null
          : (phasesList.find((p) => p.id === phaseId)?.name ?? null);

      setLocalBuildListParts((prevParts) => {
        if (!prevParts) return prevParts;
        return prevParts.map((part) =>
          part.id === buildListPart.id
            ? {
                ...part,
                build_list_phase_id: phaseId,
                phase_name: nextPhaseName,
              }
            : part
        );
      });

      try {
        await buildListPartsApi.updateBuildListPart(
          buildListId,
          buildListPart.part_id,
          { build_list_phase_id: phaseId }
        );
      } catch {
        // Revert optimistic update on error
        setLocalBuildListParts((prevParts) => {
          if (!prevParts) return prevParts;
          return prevParts.map((part) =>
            part.id === buildListPart.id
              ? {
                  ...part,
                  build_list_phase_id: prevPhaseId,
                  phase_name: prevPhaseName,
                }
              : part
          );
        });
      }
    },
    [canManageParts, buildListId, phasesList]
  );

  const handlePhaseChangeWrapper = useCallback(
    (part: BuildListPartReadWithPart, phaseId: string | null) => {
      void handlePhaseChange(part, phaseId);
    },
    [handlePhaseChange]
  );

  const parts = localBuildListParts || buildListParts || [];
  const hasCarMismatchParts =
    buildListCarId != null &&
    parts.some((p) => {
      const gp = p.part;
      if (!gp) return false;
      if (gp.is_universal) return false;
      const carIds = gp.car_ids ?? [];
      return carIds.length > 0 && !carIds.includes(buildListCarId);
    });

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
          {canManageParts && onAddPartClick && (
            <Button type="button" onClick={() => void onAddPartClick()}>
              Add Part
            </Button>
          )}
        </div>
        <ErrorAlert message="Failed to load parts. Please try again." />
      </div>
    );
  }

  const deletingPartName =
    buildListParts?.find((p) => p.id === deletingPartId)?.part.name ?? '';
  const deletingPhaseName =
    phasesList.find((p) => p.id === deletingPhaseId)?.name ?? 'phase';

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-4 flex-wrap">
          <SectionHeader title={title} />
          {/* View mode: By category | By phase */}
          <Tabs
            value={viewMode}
            onValueChange={(v) =>
              setViewMode(v as 'category' | 'phase' | 'purchased')
            }
          >
            <TabsList data-testid="build-list-view-mode-tabs">
              <TabsTrigger value="category">By category</TabsTrigger>
              <TabsTrigger value="purchased">By purchased</TabsTrigger>
              <TabsTrigger value="phase">By phase</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        {canManageParts && onAddPartClick && (
          <Button type="button" onClick={() => void onAddPartClick()}>
            Add Part
          </Button>
        )}
      </div>

      {canManageParts && viewMode === 'phase' && (
        <div className="flex items-center gap-3 flex-wrap">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setIsManagePhasesOpen(true)}
            data-testid="build-list-manage-phases-trigger"
          >
            Manage phases
          </Button>
          {phasesList.length > 0 && (
            <p className="text-xs text-gray-400">
              Drag a part onto another phase to move it, or use the phase
              dropdown on each part.
            </p>
          )}
        </div>
      )}

      {canManageParts && (
        <Dialog open={isManagePhasesOpen} onOpenChange={setIsManagePhasesOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Phases</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-gray-400 mb-3">
              Organize parts into phases or priority groups. Assign phases when
              adding or editing parts.
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
              <Input
                type="text"
                value={newPhaseName}
                onChange={(e) => setNewPhaseName(e.target.value)}
                placeholder="New phase name"
                className="w-48"
                data-testid="build-list-add-phase-input"
              />
              <Button
                type="button"
                onClick={() => void handleAddPhase()}
                disabled={!newPhaseName.trim() || isAddingPhase}
                loading={isAddingPhase}
                data-testid="build-list-add-phase-submit"
              >
                {isAddingPhase ? 'Adding...' : 'Add phase'}
              </Button>
            </div>
            {phaseError && (
              <div className="text-red-400 text-sm mb-2">{phaseError}</div>
            )}
            {phasesList.length > 0 ? (
              <ul className="space-y-2">
                {[...phasesList]
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((phase) => (
                    <li
                      key={phase.id}
                      data-testid={`build-list-phase-row-${phase.id}`}
                      className="flex items-center gap-2 py-1 border-b border-gray-700 last:border-0"
                    >
                      {editingPhaseId === phase.id ? (
                        <>
                          <Input
                            type="text"
                            value={editingPhaseName}
                            onChange={(e) =>
                              setEditingPhaseName(e.target.value)
                            }
                            className="flex-1"
                          />
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={handleCancelEditPhase}
                          >
                            Cancel
                          </Button>
                          <Button
                            type="button"
                            onClick={() => void handleSaveEditPhase()}
                          >
                            Save
                          </Button>
                        </>
                      ) : (
                        <>
                          <span className="text-gray-200 flex-1">
                            {phase.name}
                          </span>
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => handleStartEditPhase(phase)}
                          >
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => setDeletingPhaseId(phase.id)}
                            className="text-red-400 hover:text-red-300"
                          >
                            Delete
                          </Button>
                        </>
                      )}
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-500">
                No phases yet. Add one above to group parts by phase.
              </p>
            )}
          </DialogContent>
        </Dialog>
      )}

      <ConfirmDialog
        open={deletingPhaseId !== null}
        onOpenChange={handleDeletePhaseOpenChange}
        onConfirm={() => void handleDeletePhase()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the phase{' '}
            <span className="font-semibold text-foreground">
              &quot;{deletingPhaseName}&quot;
            </span>
            ? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        variant="destructive"
        error={phaseError}
        dataTestid="build-list-phase-delete-confirm"
      />

      {hasCarMismatchParts && (
        <div className="rounded-lg border border-warning/50 bg-warning/10 p-4">
          <div className="flex gap-3">
            <svg
              className="flex-shrink-0 w-5 h-5 text-warning mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <p className="text-sm font-medium text-warning">
                Possible car compatibility warning
              </p>
              <p className="text-sm text-warning/90 mt-1">
                One or more parts in this build list may be associated with a
                different car model. Parts may not be compatible across
                vehicles. Please verify fitment and do your own due diligence.
              </p>
            </div>
          </div>
        </div>
      )}

      <BuildListPartList
        buildListParts={parts}
        categories={categories || []}
        viewMode={viewMode}
        phases={phasesList}
        part_manufacturers={part_manufacturers}
        carsById={carsById}
        loading={isLoading || isLoadingCategories}
        onEdit={handleEdit}
        onDelete={handleDelete}
        {...(canManageParts && {
          onTogglePurchased: handleTogglePurchasedWrapper,
        })}
        {...(canManageParts && {
          onPhaseChange: handlePhaseChangeWrapper,
        })}
        canEdit={canManageParts}
        canDelete={canManageParts}
        canMarkPurchased={canManageParts}
        emptyMessage={emptyMessage}
        // Pass individual permission check functions
        canEditPart={canEditBuildListPart}
        canDeletePart={canDeleteBuildListPart}
        trailingTile={
          <LaborEstimatesSection
            buildListId={buildListId}
            canManage={canManageParts}
            phases={phasesList}
            {...(onLaborEstimatesChange && { onLaborEstimatesChange })}
          />
        }
      />

      {editingPart && (
        <EditBuildListPartForm
          buildListPart={editingPart}
          phases={phasesList}
          isOpen={isEditFormOpen}
          onClose={handleCloseEditForm}
          onSubmit={handleEditSubmit}
          loading={isUpdating}
        />
      )}

      {/* Delete Part Confirmation Dialog */}
      <ConfirmDialog
        open={deletingPartId !== null}
        onOpenChange={handleDeletePartOpenChange}
        onConfirm={() => void handleConfirmDelete()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to remove{' '}
            <span className="font-semibold text-foreground">
              &quot;{deletingPartName}&quot;
            </span>{' '}
            from this build list? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Removing..."
        variant="destructive"
        loading={isDeleting}
        error={deleteError}
        dataTestid="build-list-part-delete-confirm"
      />
    </div>
  );
};

export default BuildListParts;
