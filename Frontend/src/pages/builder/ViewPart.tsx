import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  PartRead,
  BuildListRead,
  CarRead,
  UserRead,
} from '../../types/Api';
import { useAuth } from '../../contexts/AuthContext';

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
import EditPartForm from '../../components/parts/EditPartForm'; 

const fetchPartRequestFn = (partId: string) =>
  apiClient.get<PartRead>(`/parts/${partId}`);

const fetchBuildListRequestFn = (buildListId: number) =>
  apiClient.get<BuildListRead>(`/build-lists/${buildListId}`);

const fetchCarRequestFn = (carId: number) =>
  apiClient.get<CarRead>(`/cars/${carId}`);

const fetchUserRequestFn = (userId: number) =>
  apiClient.get<UserRead>(`/users/${userId}`);

const deletePartRequestFn = (partId: string) =>
  apiClient.delete(`/parts/${partId}`);

function ViewPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditPartFormOpen, setIsEditPartFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [associatedBuildList, setAssociatedBuildList] =
    useState<BuildListRead | null>(null);
  const [associatedCar, setAssociatedCar] = useState<CarRead | null>(null);
  const [itemOwner, setItemOwner] = useState<UserRead | null>(null); 

  const {
    data: part,
    isLoading: isLoadingPart,
    error: partApiError,
    executeRequest: fetchPart,
  } = useApiRequest(fetchPartRequestFn);

  const {
    data: buildListData,
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
    data: ownerData,
    isLoading: isLoadingOwner,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const {
    isLoading: isDeletingPart,
    error: deletePartError,
    executeRequest: executeDeletePart,
    setError: setDeletePartError,
  } = useApiRequest<void, string>(deletePartRequestFn);

  useEffect(() => {
    if (partId) {
      fetchPart(partId);
    }
  }, [partId, fetchPart]);

  useEffect(() => {
    if (part?.build_list_id) {
      fetchBuildList(part.build_list_id);
    }
  }, [part?.build_list_id, fetchBuildList]);

  useEffect(() => {
    if (buildListData?.car_id) {
      fetchCar(buildListData.car_id);
    }
  }, [buildListData?.car_id, fetchCar]);

  useEffect(() => {
    if (carData?.user_id) {
      fetchUser(carData.user_id);
    }
  }, [carData?.user_id, fetchUser]);

  useEffect(() => {
    if (buildListData) setAssociatedBuildList(buildListData);
  }, [buildListData]);

  useEffect(() => {
    if (carData) setAssociatedCar(carData);
  }, [carData]);

  useEffect(() => {
    if (ownerData) setItemOwner(ownerData);
  }, [ownerData]);

  const handlePartUpdated = () => {
    if (partId) {
      fetchPart(partId); // Refresh part data
    }
    setIsEditPartFormOpen(false);
  };

  const openEditPartDialog = () => setIsEditPartFormOpen(true);
  const closeEditPartDialog = () => setIsEditPartFormOpen(false);

  const openDeleteConfirmDialog = () => {
    setDeletePartError(null);
    setIsDeleteConfirmOpen(true);
  };
  const closeDeleteConfirmDialog = () => setIsDeleteConfirmOpen(false);

  const handleConfirmDelete = async () => {
    if (!part || !partId) return;

    const result = await executeDeletePart(partId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      if (part.build_list_id) {
        navigate(`/build-lists/${part.build_list_id}`);
      } else {
        navigate('/builder'); // Fallback
      }
    }
  };

  const isLoading =
    isLoadingPart || isLoadingBuildList || isLoadingCar || isLoadingOwner;

  if (isLoading && !part) {
    return (
      <>
        <PageHeader title="Part Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (partApiError) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load part with ID "${partId}". ${partApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!part) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert message={`Part with ID "${partId}" not found.`} />
        </Card>
      </div>
    );
  }

  const canManage = currentUser && itemOwner && currentUser.id === itemOwner.id;

  return (
    <div>
      <PageHeader
        title={part.name}
        subtitle={
          associatedBuildList
            ? `For Build List: ${associatedBuildList.name}`
            : 'Loading...'
        }
      />
      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Part Information" />
          {canManage && (
            <div className="flex space-x-2">
              <ActionButton onClick={openEditPartDialog}>
                Edit Part
              </ActionButton>
              <ActionButton
                onClick={openDeleteConfirmDialog}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Delete Part
              </ActionButton>
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          <CardInfoItem label="Part Image">
            <ImageWithPlaceholder
              srcUrl={part.image_url}
              altText={part.name}
              imageClassName="h-48 w-auto object-contain rounded"
              containerClassName="h-48 flex justify-left items-center"
              fallbackText="No image available for this part."
            />
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          {part.description && (
            <CardInfoItem label="Description:">
              <p className="whitespace-pre-wrap">{part.description}</p>
            </CardInfoItem>
          )}
          {part.manufacturer && (
            <CardInfoItem label="Manufacturer:">
              <p>{part.manufacturer}</p>
            </CardInfoItem>
          )}
          {part.part_number && (
            <CardInfoItem label="Part Number:">
              <p>{part.part_number}</p>
            </CardInfoItem>
          )}
          {part.price !== null && part.price !== undefined && (
            <CardInfoItem label="Price:">
              <p>${part.price.toFixed(2)}</p>
            </CardInfoItem>
          )}
          {associatedBuildList && (
            <CardInfoItem label="Build List:">
              <ParentNavigationLink
                linkTo={`/build-lists/${associatedBuildList.id}`}
                linkText={associatedBuildList.name}
              />
            </CardInfoItem>
          )}
          {associatedCar && (
            <CardInfoItem label="Car:">
              <ParentNavigationLink
                linkTo={`/cars/${associatedCar.id}`}
                linkText={`${associatedCar.year} ${associatedCar.make} ${associatedCar.model}`}
              />
            </CardInfoItem>
          )}
        </div>
        {buildListApiError && (
          <ErrorAlert
            message={`Error loading build list details: ${buildListApiError}`}
          />
        )}
        {carApiError && (
          <ErrorAlert message={`Error loading car details: ${carApiError}`} />
        )}
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading owner details: ${ownerApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Part */}
      {part && canManage && (
        <Dialog
          isOpen={isEditPartFormOpen}
          onClose={closeEditPartDialog}
          title={`Edit ${part.name}`}
        >
          <EditPartForm
            part={part}
            onPartUpdated={handlePartUpdated}
            onCancel={closeEditPartDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Part Confirmation */}
      {part && canManage && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={handleConfirmDelete}
          itemName={part.name}
          itemType="part"
          isProcessing={isDeletingPart}
          error={deletePartError}
        />
      )}
    </div>
  );
}

export default ViewPart;
