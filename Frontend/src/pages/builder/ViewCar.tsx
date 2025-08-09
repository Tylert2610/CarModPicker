import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom'; 
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { CarRead, UserRead } from '../../types/Api';
import { useAuth } from '../../contexts/AuthContext';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import CardInfoItem from '../../components/common/CardInfoItem';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/Alerts';
import Divider from '../../components/layout/Divider';
import Dialog from '../../components/common/Dialog';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import BuildListList from '../../components/buildLists/BuildListList';
import ActionButton from '../../components/buttons/ActionButton';
import EditCarForm from '../../components/cars/EditCarForm';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog'; 

const fetchCarRequestFn = (carId: string) =>
  apiClient.get<CarRead>(`/cars/${carId}`);

const fetchUserRequestFn = (userId: number) =>
  apiClient.get<UserRead>(`/users/${userId}`);

const deleteCarRequestFn = (carId: string) =>
  apiClient.delete(`/cars/${carId}`); 

function ViewCar() {
  const { carId } = useParams<{ carId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate(); 
  const [isCreateBuildListFormOpen, setIsCreateBuildListFormOpen] =
    useState(false);
  const [buildListRefreshTrigger, setBuildListRefreshTrigger] = useState(0);
  const [isEditCarFormOpen, setIsEditCarFormOpen] = useState(false);
  const [carOwner, setCarOwner] = useState<UserRead | null>(null);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false); 

  const {
    data: car,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const { data: userData, executeRequest: fetchUser } =
    useApiRequest(fetchUserRequestFn);

  const {
    isLoading: isDeletingCar,
    error: deleteCarError,
    executeRequest: executeDeleteCar,
    setError: setDeleteCarError,
  } = useApiRequest<void, string>(deleteCarRequestFn);

  useEffect(() => {
    if (carId) {
      fetchCar(carId);
    }
  }, [carId, fetchCar]);

  // useEffect to fetch user data when car data is available
  useEffect(() => {
    if (car?.user_id) {
      fetchUser(car.user_id);
    }
  }, [car?.user_id, fetchUser]);

  // Update carOwner state when userData changes
  useEffect(() => {
    if (userData) {
      setCarOwner(userData);
    }
  }, [userData]);

  const handleBuildListCreated = () => {
    setBuildListRefreshTrigger((prev) => prev + 1);
    setIsCreateBuildListFormOpen(false); // Close dialog
  };

  const openCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(true);
  };

  const closeCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(false);
  };

  const openEditCarDialog = () => {
    setIsEditCarFormOpen(true);
  };

  const closeEditCarDialog = () => {
    setIsEditCarFormOpen(false);
  };

  const handleCarUpdated = () => {
    if (carId) {
      fetchCar(carId);
    }
    setIsEditCarFormOpen(false);
  };

  const openDeleteConfirmDialog = () => {
    setDeleteCarError(null); // Clear previous errors
    setIsDeleteConfirmOpen(true);
  };

  const closeDeleteConfirmDialog = () => {
    setIsDeleteConfirmOpen(false);
  };

  const handleConfirmDelete = async () => {
    if (!car || !carId) return;

    const result = await executeDeleteCar(carId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      navigate('/builder');
    }
  };

  if (isLoadingCar) {
    return (
      <>
        <PageHeader title="Car Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (carApiError) {
    return (
      <div>
        <PageHeader title="Car Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load car with ID "${carId}". ${carApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!car) {
    return (
      <div>
        <PageHeader title="Car Details" />
        <Card>
          <ErrorAlert message={`Car with ID "${carId}" not found.`} />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={`${car.year} ${car.make} ${car.model}`} />
      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Car Information" />
          {currentUser && currentUser.id === car.user_id && (
            <div className="flex space-x-2">
              <ActionButton onClick={openEditCarDialog}>Edit Car</ActionButton>
              <ActionButton
                onClick={openDeleteConfirmDialog}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Delete Car
              </ActionButton>
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          <CardInfoItem label="">
            <ImageWithPlaceholder
              srcUrl={car.image_url}
              altText={`${car.year} ${car.make} ${car.model}`}
              imageClassName="h-48 w-auto object-contain rounded"
              containerClassName="h-48 flex justify-left items-center"
              fallbackText="No image available."
            />
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          <CardInfoItem label="User:">
            <ParentNavigationLink
              linkTo={`/user/${car.user_id}`}
              linkText={
                carOwner ? `${carOwner.username}` : `User ${car.user_id}`
              }
            />
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          <CardInfoItem label="Make:">
            <p>{car.make}</p>
          </CardInfoItem>
          <CardInfoItem label="Model:">
            <p>{car.model}</p>
          </CardInfoItem>
          <CardInfoItem label="Year:">
            <p>{car.year}</p>
          </CardInfoItem>
          {car.trim && (
            <CardInfoItem label="Trim:">
              <p>{car.trim}</p>
            </CardInfoItem>
          )}
          {car.vin && (
            <CardInfoItem label="VIN:">
              <p>{car.vin}</p>
            </CardInfoItem>
          )}
        </div>
      </Card>

      <Divider />

      {/* Dialog for Editing Car */}
      {car && (
        <Dialog
          isOpen={isEditCarFormOpen}
          onClose={closeEditCarDialog}
          title={`Edit ${car.make} ${car.model}`}
        >
          <EditCarForm
            car={car}
            onCarUpdated={handleCarUpdated}
            onCancel={closeEditCarDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Car Confirmation */}
      {car && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={handleConfirmDelete}
          itemName={`${car.year} ${car.make} ${car.model}`}
          itemType="car"
          isProcessing={isDeletingCar}
          error={deleteCarError}
        />
      )}

      {/* Dialog for Creating Build List */}
      <Dialog
        isOpen={isCreateBuildListFormOpen}
        onClose={closeCreateBuildListDialog}
        title={`Create Build List for ${car.make} ${car.model}`}
      >
        <CreateBuildListForm
          carId={car.id}
          onBuildListCreated={handleBuildListCreated}
        />
      </Dialog>

      {/* Build Lists Section */}
      <BuildListList
        carId={car.id}
        carOwnerId={car.user_id}
        currentUserId={currentUser?.id}
        refreshKey={buildListRefreshTrigger}
        title={`Build Lists for ${car.make} ${car.model}`}
        emptyMessage="This car doesn't have any build lists yet."
        onAddBuildListClick={
          currentUser && currentUser.id === car.user_id
            ? openCreateBuildListDialog
            : undefined
        }
      />
    </div>
  );
}

export default ViewCar;
