import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { BuildListRead, CarRead, UserRead } from '../../types/Api';
import { useAuth } from '../../hooks/useAuth';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import CardInfoItem from '../../components/common/CardInfoItem';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/Alerts';
import Divider from '../../components/layout/Divider';
import Dialog from '../../components/common/Dialog';
import ActionButton from '../../components/buttons/ActionButton';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import EditBuildListForm from '../../components/buildLists/EditBuildListForm';
import CreateBuildListPartForm from '../../components/buildListParts/CreateBuildListPartForm';
import BuildListParts from '../../components/buildListParts/BuildListParts';

const fetchBuildListRequestFn = (buildListId: string) =>
  apiClient.get<BuildListRead>(`/build-lists/${buildListId}`);

const fetchCarRequestFn = (
  carId: number // carId is number
) => apiClient.get<CarRead>(`/cars/${carId}`);

const fetchUserRequestFn = (userId: number) =>
  apiClient.get<UserRead>(`/users/${userId}`);

const deleteBuildListRequestFn = (buildListId: string) =>
  apiClient.delete<Record<string, string>>(`/build-lists/${buildListId}`);

function ViewBuildList() {
  const { buildListId } = useParams<{ buildListId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditBuildListFormOpen, setIsEditBuildListFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] =
    useState<boolean>(false);
  const [associatedCar, setAssociatedCar] = useState<CarRead | null>(null);
  const [carOwner, setCarOwner] = useState<UserRead | null>(null);
  const [partsRefreshTrigger, setPartsRefreshTrigger] = useState<number>(0);
  const [isCreatePartFormOpen, setIsCreatePartFormOpen] = useState(false);

  const {
    data: buildList,
    isLoading: isLoadingBuildList,
    error: buildListApiError,
    executeRequest: fetchBuildList,
  } = useApiRequest(fetchBuildListRequestFn);

  const {
    data: carData,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const {
    data: userData,
    isLoading: isLoadingOwner,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const {
    isLoading: isDeletingBuildList,
    error: deleteBuildListError,
    executeRequest: executeDeleteBuildList,
    setError: setDeleteBuildListError,
  } = useApiRequest(deleteBuildListRequestFn);

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
    if (carData?.user_id) {
      void fetchUser(carData.user_id);
    }
  }, [carData?.user_id, fetchUser]);

  useEffect(() => {
    if (carData) {
      setAssociatedCar(carData);
    }
  }, [carData]);

  useEffect(() => {
    if (userData) {
      setCarOwner(userData);
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
  const closeDeleteConfirmDialog = () => setIsDeleteConfirmOpen(false);

  const handleConfirmDelete = async () => {
    if (!buildList || !buildListId) return;

    const result = await executeDeleteBuildList(buildListId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      if (buildList.car_id) {
        void navigate(`/cars/${buildList.car_id}`);
      } else {
        void navigate('/builder');
      }
    }
  };

  // Handlers for Part creation
  const handlePartAdded = () => {
    setPartsRefreshTrigger(partsRefreshTrigger + 1); // Trigger BuildListParts refresh
    setIsCreatePartFormOpen(false); // Close dialog
  };

  const openCreatePartDialog = () => setIsCreatePartFormOpen(true);
  const closeCreatePartDialog = () => setIsCreatePartFormOpen(false);

  const isLoading = isLoadingBuildList || isLoadingCar || isLoadingOwner;

  if (isLoading && !buildList) {
    return (
      <>
        <PageHeader title="Build List Details" />
        <LoadingSpinner />
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

  const canManage = currentUser && carOwner && currentUser.id === carOwner.id;

  return (
    <div>
      <PageHeader
        title={buildList.name}
        subtitle={`For car: ${associatedCar ? `${associatedCar.year} ${associatedCar.make} ${associatedCar.model}` : 'Loading...'}`}
      />
      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Build List Information" />
          {canManage && (
            <div className="flex space-x-2">
              <ActionButton onClick={openEditBuildListDialog}>
                Edit Build List
              </ActionButton>
              <ActionButton
                onClick={openDeleteConfirmDialog}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Delete Build List
              </ActionButton>
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          <CardInfoItem label="">
            <ImageWithPlaceholder
              srcUrl={buildList.image_url}
              altText={buildList.name}
              imageClassName="h-48 w-auto object-contain rounded"
              containerClassName="h-48 flex justify-left items-center"
              fallbackText="No image available for this build list."
            />
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          <CardInfoItem label="Description:">
            <p>{buildList.description || 'No description provided.'}</p>
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          {associatedCar && (
            <CardInfoItem label="Associated Car:">
              <ParentNavigationLink
                linkTo={`/cars/${associatedCar.id}`}
                linkText={`${associatedCar.year} ${associatedCar.make} ${associatedCar.model}`}
              />
            </CardInfoItem>
          )}
          {carOwner && (
            <CardInfoItem label="Owner:">
              <ParentNavigationLink
                linkTo={`/user/${carOwner.id}`}
                linkText={carOwner.username}
              />
            </CardInfoItem>
          )}
          <CardInfoItem label="Build List ID:">
            <p>{buildList.id}</p>
          </CardInfoItem>
        </div>
        {carApiError && (
          <ErrorAlert
            message={`Error loading associated car details: ${carApiError}`}
          />
        )}
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading owner details: ${ownerApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Build List */}
      {buildList && canManage && (
        <Dialog
          isOpen={isEditBuildListFormOpen}
          onClose={closeEditBuildListDialog}
          title={`Edit ${buildList.name}`}
        >
          <EditBuildListForm
            buildList={buildList}
            onBuildListUpdated={handleBuildListUpdated}
            onCancel={closeEditBuildListDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Build List Confirmation */}
      {buildList && canManage && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={() => void handleConfirmDelete()}
          itemName={buildList.name}
          itemType="build list"
          isProcessing={isDeletingBuildList}
          error={deleteBuildListError}
        />
      )}

      {/* Dialog for Creating Part */}
      {buildList && canManage && (
        <Dialog
          isOpen={isCreatePartFormOpen}
          onClose={closeCreatePartDialog}
          title="Add Part to Build List"
        >
          <CreateBuildListPartForm
            buildListId={buildList.id}
            onPartAdded={handlePartAdded}
            onCancel={closeCreatePartDialog}
          />
        </Dialog>
      )}

      {/* Parts Section */}
      {buildList && (
        <BuildListParts
          buildListId={buildList.id}
          canManageParts={canManage || false}
          refreshKey={partsRefreshTrigger}
          onAddPartClick={canManage ? openCreatePartDialog : undefined}
          title={`Parts in ${buildList.name}`}
          emptyMessage="This build list currently has no parts."
        />
      )}
    </div>
  );
}

export default ViewBuildList;
