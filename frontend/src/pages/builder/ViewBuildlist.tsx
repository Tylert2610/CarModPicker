import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { useDocumentMeta } from '../../hooks/useDocumentMeta';
import { buildListsApi } from '../../api/build_lists';
import { apiClient } from '../../api/client';
import { buildListVotesApi } from '../../api/votes';
import type {
  BuildListLaborEstimateRead,
  BuildListPartReadWithPart,
  BuildListRead,
  CarGenerationRead,
  UserRead,
  VoteSummary,
} from '../../types/Api';

import { Link } from 'react-router-dom';
import BuildCostSummary from '../../components/buildListParts/BuildCostSummary';
import BuildListParts from '../../components/buildListParts/BuildListParts';
import CreateBuildListPartForm from '../../components/buildListParts/CreateBuildListPartForm';
import EditBuildListForm from '../../components/buildLists/EditBuildListForm';
import ImageGalleryManage from '../../components/images/ImageGalleryManage';
import ImageUpload from '../../components/forms/ImageUpload';
import ImageGallery from '../../components/parts/ImageGallery';
import VoteButtons from '../../components/parts/VoteButtons';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import CardInfoItem from '../../components/ui/card-info-item';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import Spinner from '../../components/ui/spinner';
import { carFullDisplayName, formatCarYearRange } from '../../utils/carUtils';

const fetchBuildListRequestFn = (buildListId: string) =>
  apiClient.get<BuildListRead>(`/build-lists/${buildListId}`);

const fetchCarRequestFn = (carId: string) =>
  apiClient.get<CarGenerationRead>(`/car-generations/${carId}`);

const fetchUserRequestFn = (userId: string) =>
  apiClient.get<UserRead>(`/users/${userId}`);

const fetchVoteSummaryRequestFn = (buildListId: string) =>
  buildListVotesApi.getVoteSummary(buildListId);

const deleteBuildListRequestFn = (buildListId: string) =>
  apiClient.delete<Record<string, string>>(`/build-lists/${buildListId}`);

function ViewBuildList() {
  const { buildListId } = useParams<{ buildListId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditBuildListFormOpen, setIsEditBuildListFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] =
    useState<boolean>(false);
  const [associatedCar, setAssociatedCar] = useState<CarGenerationRead | null>(
    null
  );
  const [buildListOwner, setBuildListOwner] = useState<UserRead | null>(null);
  const [partsRefreshTrigger, setPartsRefreshTrigger] = useState<number>(0);
  const [isCreatePartFormOpen, setIsCreatePartFormOpen] = useState(false);
  const [voteSummary, setVoteSummary] = useState<VoteSummary | null>(null);
  const [buildListParts, setBuildListParts] = useState<
    BuildListPartReadWithPart[]
  >([]);
  const handlePartsChange = useCallback(
    (parts: BuildListPartReadWithPart[]) => {
      setBuildListParts(parts);
    },
    []
  );
  const [laborEstimates, setLaborEstimates] = useState<
    BuildListLaborEstimateRead[]
  >([]);
  const handleLaborEstimatesChange = useCallback(
    (items: BuildListLaborEstimateRead[]) => {
      setLaborEstimates(items);
    },
    []
  );

  const {
    data: buildList,
    isLoading: isLoadingBuildList,
    error: buildListApiError,
    executeRequest: fetchBuildList,
  } = useApiRequest(fetchBuildListRequestFn);

  useDocumentMeta({
    title: buildList?.name ?? 'Build List',
    description: buildList?.description
      ? buildList.description.slice(0, 160)
      : buildList?.name
        ? `Parts, photos, and build log for ${buildList.name} on CarModPicker.`
        : 'View a community build — parts list, photos, build log, and costs on CarModPicker.',
    canonicalPath: buildListId ? `/build-lists/${buildListId}` : undefined,
  });

  const {
    data: carData,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const {
    data: userData,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const { data: voteSummaryData, executeRequest: fetchVoteSummary } =
    useApiRequest(fetchVoteSummaryRequestFn);

  const {
    isLoading: isDeletingBuildList,
    error: deleteBuildListError,
    executeRequest: executeDeleteBuildList,
    setError: setDeleteBuildListError,
  } = useApiRequest(deleteBuildListRequestFn);

  const copyBuildListRequestFn = (buildListId: string) =>
    apiClient.post<BuildListRead>(`/build-lists/${buildListId}/copy`, {
      new_name: null,
    });

  const {
    isLoading: isCopyingBuildList,
    error: copyBuildListError,
    executeRequest: executeCopyBuildList,
    setError: setCopyBuildListError,
  } = useApiRequest(copyBuildListRequestFn);

  useEffect(() => {
    if (buildListId) {
      void fetchBuildList(buildListId);
    }
  }, [buildListId, fetchBuildList]);

  useEffect(() => {
    if (buildList?.car_id) {
      void fetchCar(buildList.car_id);
    }
  }, [buildList?.car_id, fetchCar]);

  useEffect(() => {
    if (carData) {
      setAssociatedCar(carData);
    }
  }, [carData]);

  useEffect(() => {
    if (buildList?.user_id) {
      void fetchUser(buildList.user_id);
    }
  }, [buildList?.user_id, fetchUser]);

  useEffect(() => {
    if (buildListId) {
      void fetchVoteSummary(buildListId);
    }
  }, [buildListId, fetchVoteSummary]);

  useEffect(() => {
    if (voteSummaryData) {
      setVoteSummary(voteSummaryData);
    }
  }, [voteSummaryData]);

  const handleVoteUpdate = (
    _entityId: string,

    _newVote: 'upvote' | 'downvote' | null
  ) => {
    // Refresh vote summary after voting
    if (buildListId) {
      void fetchVoteSummary(buildListId);
    }
  };

  useEffect(() => {
    if (userData) {
      setBuildListOwner(userData);
    }
  }, [userData]);

  const handleBuildListUpdated = () => {
    if (buildListId) {
      void fetchBuildList(buildListId); // Refresh build list data
    }
    setIsEditBuildListFormOpen(false);
  };

  const openEditBuildListDialog = () => setIsEditBuildListFormOpen(true);
  const closeEditBuildListDialog = () => setIsEditBuildListFormOpen(false);

  const openDeleteConfirmDialog = () => {
    setDeleteBuildListError(null);
    setIsDeleteConfirmOpen(true);
  };

  const handleDeleteOpenChange = (open: boolean) => {
    if (!open && isDeletingBuildList) return;
    setIsDeleteConfirmOpen(open);
  };

  const handleConfirmDelete = async () => {
    if (!buildList || !buildListId) return;

    const result = await executeDeleteBuildList(buildListId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      if (buildList.car_id) {
        void navigate(`/car-generations/${buildList.car_id}`);
      } else {
        void navigate('/builder');
      }
    }
  };

  const handleCopyBuildList = async () => {
    if (!buildList || !buildListId) return;

    setCopyBuildListError(null);
    const result = await executeCopyBuildList(buildListId);
    if (result !== null) {
      // Navigate to the newly copied build list
      void navigate(`/build-lists/${result.id}`);
    }
  };

  // Handlers for Part creation
  const handlePartAdded = () => {
    setPartsRefreshTrigger(partsRefreshTrigger + 1); // Trigger BuildListParts refresh
    setIsCreatePartFormOpen(false); // Close dialog
  };

  const openCreatePartDialog = () => setIsCreatePartFormOpen(true);
  const closeCreatePartDialog = () => setIsCreatePartFormOpen(false);

  const isLoading = isLoadingBuildList || isLoadingCar;

  if (isLoading && !buildList) {
    return (
      <>
        <PageHeader title="Build List Details" />
        <Spinner />
      </>
    );
  }

  if (buildListApiError) {
    return (
      <div>
        <PageHeader title="Build List Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load build list with ID "${buildListId}". ${buildListApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!buildList) {
    return (
      <div>
        <PageHeader title="Build List Details" />
        <Card>
          <ErrorAlert
            message={`Build list with ID "${buildListId}" not found.`}
          />
        </Card>
      </div>
    );
  }

  // Check if current user owns the build list (build lists have their own user_id)
  const canManage =
    currentUser && buildList && currentUser.id === buildList.user_id;

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={buildList.name}
        subtitle={`For car: ${associatedCar ? `${carFullDisplayName(associatedCar)} (${formatCarYearRange(associatedCar.start_year, associatedCar.end_year)})` : buildList.car_id ? 'Loading...' : 'No car assigned'}`}
      />

      {/* Warning when build list has no car assigned */}
      {!buildList.car_id && (
        <Card className="mb-6 border-2 border-yellow-600 bg-yellow-900/20">
          <div className="p-6">
            <div className="flex items-start space-x-4">
              <div className="text-4xl">⚠️</div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-yellow-300 mb-2">
                  Car Assignment Required
                </h3>
                <p className="text-yellow-200 mb-4">
                  This build list doesn't have a car assigned.
                  {canManage
                    ? ' Please assign a car to help organize your build list and make it easier for others to find.'
                    : ' The owner should assign a car to help organize this build list.'}
                </p>
                {canManage && (
                  <Button
                    type="button"
                    onClick={openEditBuildListDialog}
                    className="bg-yellow-600 hover:bg-yellow-700 text-white"
                  >
                    Assign Car Now
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex flex-col gap-3 mb-4 sm:flex-row sm:justify-between sm:items-center sm:gap-4">
          <SectionHeader title="Build List Information" />
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <Button
              type="button"
              onClick={() =>
                void navigate(`/build-lists/${buildList.id}/build-log`)
              }
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              View Build Log
            </Button>
            {currentUser && (
              <Button
                type="button"
                onClick={() => void handleCopyBuildList()}
                loading={isCopyingBuildList}
                className="bg-info hover:bg-info/90 text-white"
              >
                {isCopyingBuildList ? 'Copying...' : 'Copy Build List'}
              </Button>
            )}
            {canManage && (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={openEditBuildListDialog}
                  data-testid="build-list-edit-trigger"
                >
                  Edit Build List
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={openDeleteConfirmDialog}
                  data-testid="build-list-delete-trigger"
                >
                  Delete Build List
                </Button>
              </>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 items-start">
          <div className="min-w-0 space-y-3">
            {canManage ? (
              <ImageGalleryManage
                imageUrls={buildList.image_urls ?? null}
                altText={buildList.name}
                onSetPrimary={(idx) =>
                  buildListsApi.setBuildListPrimaryImage(buildList.id, idx)
                }
                onRemove={(idx) =>
                  buildListsApi.removeBuildListImage(buildList.id, idx)
                }
                onUpdated={() => {
                  void fetchBuildList(buildList.id);
                }}
                layout="hero"
                emptyMessage="No images available for this build list."
              />
            ) : (
              <ImageGallery
                imageUrls={buildList.image_urls ?? null}
                altText={buildList.name}
                layout="hero"
                emptyMessage="No image available for this build list."
              />
            )}
            {canManage && (buildList.image_urls?.length ?? 0) < 12 && (
              <ImageUpload
                key={`bl-image-add-${buildList.image_urls?.length ?? 0}`}
                entityType="build_list"
                entityId={buildList.id}
                showPreview={false}
                label="Add Image"
                maxSizeMB={10}
                onImageUploaded={(fileKey) => {
                  void (async () => {
                    try {
                      await buildListsApi.appendBuildListImages(buildList.id, [
                        fileKey,
                      ]);
                      await fetchBuildList(buildList.id);
                    } catch {
                      // Errors surface via the gallery's own error UI on next action;
                      // a transient failure here is rare since the upload already succeeded.
                    }
                  })();
                }}
              />
            )}
          </div>
          <div className="min-w-0 space-y-2.5">
            {(buildListParts.length > 0 ||
              laborEstimates.length > 0 ||
              buildList.base_price_cents > 0) && (
              <CardInfoItem label="Build Cost:">
                <BuildCostSummary
                  buildListParts={buildListParts}
                  laborEstimates={laborEstimates}
                  basePriceCents={buildList.base_price_cents}
                  className="mt-1"
                />
              </CardInfoItem>
            )}
            <CardInfoItem label="Description:">
              <p>{buildList.description || 'No description provided.'}</p>
            </CardInfoItem>
            {associatedCar && (
              <CardInfoItem label="Associated Car:">
                <Link
                  to={`/car-generations/${associatedCar.id}`}
                  className="text-info hover:text-info/90 underline"
                >
                  {`${carFullDisplayName(associatedCar)} (${formatCarYearRange(associatedCar.start_year, associatedCar.end_year)})`}
                </Link>
              </CardInfoItem>
            )}
            {buildListOwner && (
              <CardInfoItem label="Build List Owner:">
                <Link
                  to={`/user/${buildListOwner.id}`}
                  className="text-info hover:text-info/90 underline"
                >
                  {buildListOwner.username}
                </Link>
              </CardInfoItem>
            )}
            {voteSummary && (
              <CardInfoItem label="Community Rating:">
                <VoteButtons
                  entityId={buildList.id}
                  upvotes={voteSummary.upvotes}
                  downvotes={voteSummary.downvotes}
                  userVote={voteSummary.user_vote ?? null}
                  onVoteUpdate={handleVoteUpdate}
                  voteApi={{
                    voteOnEntity: (
                      id: string,
                      data: { vote_type: 'upvote' | 'downvote' }
                    ) => buildListVotesApi.voteOnBuildList(id, data),
                    removeVote: (id: string) =>
                      buildListVotesApi.removeVote(id),
                  }}
                  size="md"
                />
              </CardInfoItem>
            )}
          </div>
        </div>
        {carApiError && (
          <ErrorAlert
            message={`Error loading associated car details: ${carApiError}`}
          />
        )}
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading build list owner details: ${ownerApiError}`}
          />
        )}
        {copyBuildListError && (
          <ErrorAlert
            message={`Error copying build list: ${copyBuildListError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Build List */}
      {buildList && canManage && (
        <Dialog
          open={isEditBuildListFormOpen}
          onOpenChange={setIsEditBuildListFormOpen}
        >
          <DialogContent
            data-testid="build-list-edit-dialog"
            className="sm:max-w-2xl"
          >
            <DialogHeader>
              <DialogTitle>{`Edit ${buildList.name}`}</DialogTitle>
            </DialogHeader>
            <EditBuildListForm
              buildList={buildList}
              onBuildListUpdated={handleBuildListUpdated}
              onCancel={closeEditBuildListDialog}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Dialog for Deleting Build List Confirmation */}
      {buildList && canManage && (
        <ConfirmDialog
          open={isDeleteConfirmOpen}
          onOpenChange={handleDeleteOpenChange}
          onConfirm={() => void handleConfirmDelete()}
          title="Confirm Deletion"
          description={
            <>
              Are you sure you want to delete the build list{' '}
              <span className="font-semibold text-foreground">
                &quot;{buildList.name}&quot;
              </span>
              ? This action cannot be undone.
            </>
          }
          confirmLabel="Confirm Delete"
          loadingLabel="Deleting..."
          variant="destructive"
          loading={isDeletingBuildList}
          error={deleteBuildListError}
          dataTestid="build-list-delete-confirm"
        />
      )}

      {/* Dialog for Creating Part */}
      {buildList && canManage && (
        <Dialog
          open={isCreatePartFormOpen}
          onOpenChange={setIsCreatePartFormOpen}
        >
          <DialogContent
            data-testid="build-list-add-part-dialog"
            className="sm:max-w-[64rem]"
          >
            <DialogHeader>
              <DialogTitle>Add Part to Build List</DialogTitle>
            </DialogHeader>
            <CreateBuildListPartForm
              buildListId={buildList.id}
              onPartAdded={handlePartAdded}
              onCancel={closeCreatePartDialog}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Parts + Labor Estimates Section (labor renders as a tile in the parts masonry) */}
      {buildList && (
        <BuildListParts
          buildListId={buildList.id}
          buildListCarId={buildList.car_id ?? null}
          canManageParts={canManage || false}
          refreshKey={partsRefreshTrigger}
          onPartsChange={handlePartsChange}
          onLaborEstimatesChange={handleLaborEstimatesChange}
          {...(canManage && { onAddPartClick: openCreatePartDialog })}
          title={`Parts in ${buildList.name}`}
          emptyMessage="This build list currently has no parts."
        />
      )}
    </div>
  );
}

export default ViewBuildList;
