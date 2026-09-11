import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { buildListPartsApi } from '../../api/build_list_parts';
import { buildListsApi } from '../../api/build_lists';
import type {
  BuildListPartCreate,
  BuildListPhaseRead,
  BuildListRead,
  PartReadWithVotes,
} from '../../types/Api';

import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import Spinner from '../ui/spinner';

interface AddToBuildListDialogProps {
  isOpen: boolean;
  onClose: () => void;
  part: PartReadWithVotes | null;
  onPartAdded: () => void;
}

/**
 * Adds a part to one or more of the user's build lists, with quantity and optional phase.
 */
function AddToBuildListDialog({
  isOpen,
  onClose,
  part,
  onPartAdded,
}: AddToBuildListDialogProps) {
  const { user } = useAuth();
  const [selectedBuildListIds, setSelectedBuildListIds] = useState<Set<string>>(
    () => new Set()
  );
  const [quantity, setQuantity] = useState(1);
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildLists, setBuildLists] = useState<BuildListRead[]>([]);
  const [isLoadingBuildLists, setIsLoadingBuildLists] = useState(false);
  const [buildListsError, setBuildListsError] = useState<string | null>(null);
  const [phases, setPhases] = useState<BuildListPhaseRead[]>([]);
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null);

  const singleSelectedBuildListId =
    selectedBuildListIds.size === 1
      ? Array.from(selectedBuildListIds)[0]
      : null;

  const toggleBuildListSelection = (id: string) => {
    setSelectedBuildListIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const hasCarMismatch =
    part != null &&
    !part.is_universal &&
    (part.car_ids?.length ?? 0) > 0 &&
    Array.from(selectedBuildListIds).some((blId) => {
      const buildList = buildLists.find((bl) => bl.id === blId);
      return (
        buildList?.car_id != null && !part.car_ids.includes(buildList.car_id)
      );
    });

  useEffect(() => {
    if (isOpen && user) {
      const fetchUserBuildLists = async () => {
        try {
          setIsLoadingBuildLists(true);
          const response = await buildListsApi.getBuildListsByUser(user.id);
          setBuildLists(response.data);
        } catch (error) {
          setBuildListsError(
            error instanceof Error
              ? error.message
              : 'Failed to load build lists'
          );
        } finally {
          setIsLoadingBuildLists(false);
        }
      };

      void fetchUserBuildLists();
    }
  }, [isOpen, user]);

  useEffect(() => {
    if (isOpen) {
      setSelectedBuildListIds(new Set());
      setQuantity(1);
      setError(null);
      setPhases([]);
      setSelectedPhaseId(null);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedPhaseId(null);
    if (singleSelectedBuildListId == null) {
      setPhases([]);
      return;
    }
    let cancelled = false;
    const fetchPhases = async () => {
      try {
        const response = await buildListsApi.getPhases(
          singleSelectedBuildListId
        );
        if (!cancelled) setPhases(response.data);
      } catch {
        if (!cancelled) setPhases([]);
      }
    };
    void fetchPhases();
    return () => {
      cancelled = true;
    };
  }, [singleSelectedBuildListId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!part || selectedBuildListIds.size === 0) {
      setError('Please select at least one build list');
      return;
    }

    setIsAdding(true);
    setError(null);

    const buildListPartData: BuildListPartCreate = {
      quantity: Math.max(1, quantity),
      notes: null,
      ...(singleSelectedBuildListId != null &&
        selectedPhaseId != null && {
          build_list_phase_id: selectedPhaseId,
        }),
    };

    try {
      for (const buildListId of selectedBuildListIds) {
        await buildListPartsApi.addPartToBuildList(
          buildListId,
          part.id,
          buildListPartData
        );
      }

      onPartAdded();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to add part to build list'
      );
    } finally {
      setIsAdding(false);
    }
  };

  if (!part) {
    return null;
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        data-testid="parts-catalog-add-to-build-list-dialog"
        className="sm:max-w-3xl max-h-[90vh] overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle>{`Add ${part.name} to Build List`}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            void handleSubmit(e);
          }}
          className="space-y-6"
        >
          {error && <ErrorAlert message={error} />}

          <Card>
            <div className="mb-4">
              <p className="text-sm text-muted-foreground">
                This will add the part to your build list where you can add
                notes and customize it.
              </p>
            </div>
            <div className="flex gap-4">
              <div className="flex-shrink-0">
                <ImageWithPlaceholder
                  srcUrl={part.image_urls?.[0] ?? null}
                  altText={part.name}
                  imageClassName="w-24 h-24 object-cover rounded-lg"
                  containerClassName="w-24 h-24 flex justify-center items-center"
                  fallbackText="No image"
                />
              </div>
              <div className="flex-grow">
                <h3 className="text-xl font-semibold text-white mb-2">
                  {part.name}
                </h3>
                {part.part_manufacturer && (
                  <p className="text-sm text-gray-400 mb-1">
                    {part.part_manufacturer}
                  </p>
                )}
                {part.best_price_cents != null && (
                  <p className="text-sm font-medium text-green-400">
                    ${(part.best_price_cents / 100).toFixed(2)}
                  </p>
                )}
                {part.description && (
                  <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                    {part.description.length > 120
                      ? `${part.description.slice(0, 120).trim()}…`
                      : part.description}
                  </p>
                )}
              </div>
            </div>
          </Card>

          <div className="space-y-2">
            <label
              htmlFor="add-to-build-list-quantity"
              className="block text-sm font-medium text-foreground"
            >
              Quantity
            </label>
            <input
              id="add-to-build-list-quantity"
              type="number"
              min={1}
              max={999}
              value={quantity}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!Number.isNaN(v) && v >= 1) setQuantity(v);
              }}
              className="w-24 px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
            />
          </div>

          <div className="space-y-4">
            <h3 className="text-xl font-semibold text-foreground">
              Select Build List(s)
            </h3>
            <p className="text-sm text-muted-foreground">
              Select one or more build lists, then add the part to all selected
              at once.
            </p>

            {isLoadingBuildLists ? (
              <Spinner />
            ) : buildListsError ? (
              <ErrorAlert message="Failed to load build lists" />
            ) : buildLists && buildLists.length > 0 ? (
              <div className="max-h-64 overflow-y-auto space-y-1">
                {buildLists.map((buildList: BuildListRead) => {
                  const isSelected = selectedBuildListIds.has(buildList.id);
                  const isCarMismatch =
                    !part.is_universal &&
                    (part.car_ids?.length ?? 0) > 0 &&
                    buildList.car_id != null &&
                    !part.car_ids.includes(buildList.car_id);
                  return (
                    <Card
                      key={buildList.id}
                      padding="sm"
                      className={`cursor-pointer transition-all duration-200 flex items-center gap-2 py-2 px-3 min-h-0 ${
                        isSelected
                          ? 'border-2 border-primary bg-primary/25 shadow-md ring-2 ring-primary/30'
                          : 'border border-transparent hover:bg-white/5 hover:border-white/20'
                      }`}
                      onClick={() => toggleBuildListSelection(buildList.id)}
                    >
                      <div
                        className={`flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                          isSelected
                            ? 'bg-primary border-primary'
                            : 'border-border bg-transparent'
                        }`}
                      >
                        {isSelected && (
                          <svg
                            className="w-2.5 h-2.5 text-white"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2.5}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        )}
                      </div>
                      <div className="flex-grow min-w-0 flex items-center gap-2 overflow-hidden">
                        <span className="text-sm font-medium text-gray-200 truncate">
                          {buildList.name}
                        </span>
                        {isCarMismatch && (
                          <span
                            className="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-warning/20 text-warning border border-warning/40"
                            title="This build list is for a different car model than this part"
                          >
                            Different car
                          </span>
                        )}
                        {buildList.description && (
                          <span className="flex-shrink text-xs text-gray-500 truncate max-w-[8rem]">
                            {buildList.description.length > 40
                              ? `${buildList.description.slice(0, 40).trim()}…`
                              : buildList.description}
                          </span>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-6 text-muted-foreground">
                <p>No build lists found.</p>
                <p className="text-sm mt-2">
                  Create a build list first to add parts to it.
                </p>
              </div>
            )}
          </div>

          {singleSelectedBuildListId != null && phases.length > 0 && (
            <div className="space-y-2">
              <label
                htmlFor="add-to-build-list-phase"
                className="block text-sm font-medium text-foreground"
              >
                Phase
              </label>
              <select
                id="add-to-build-list-phase"
                value={selectedPhaseId ?? ''}
                onChange={(e) => {
                  const v = e.target.value;
                  setSelectedPhaseId(v === '' ? null : v);
                }}
                className="block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm text-white focus:outline-none focus:ring-info focus:border-info sm:text-sm"
              >
                <option value="">None</option>
                {[...phases]
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((phase) => (
                    <option key={phase.id} value={phase.id}>
                      {phase.name}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {hasCarMismatch && (
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
                    Car mismatch
                  </p>
                  <p className="text-sm text-warning/90 mt-1">
                    This part is associated with a different car model than one
                    or more of the selected build lists. Parts may not be
                    compatible across vehicles. Please verify fitment and do
                    your own due diligence before adding.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={isAdding}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={isAdding}
              disabled={selectedBuildListIds.size === 0}
              data-testid="parts-catalog-add-to-build-list-submit"
            >
              {selectedBuildListIds.size === 1
                ? 'Add to Build List'
                : `Add to ${selectedBuildListIds.size} Build Lists`}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default AddToBuildListDialog;
