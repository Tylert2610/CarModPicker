import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { useDocumentMeta } from '../../hooks/useDocumentMeta';
import { carGenerationsApi } from '../../api/car_generations';

import BuildListList from '../../components/buildLists/BuildListList';
import CreateBuildListForm from '../../components/buildLists/CreateBuildListForm';
import {
  carFullDisplayName,
  carGenerationDisplayName,
  carModelDisplayName,
  formatCarYearRange,
} from '../../utils/carUtils';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Card } from '../../components/ui/card';
import CardInfoItem from '../../components/ui/card-info-item';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import Spinner from '../../components/ui/spinner';

const fetchCarRequestFn = (carId: string) => carGenerationsApi.getCar(carId);

/** Detail page for one car and the build lists attached to it. */
function ViewCar(): React.JSX.Element {
  const { carId } = useParams<{ carId: string }>();
  const { user: currentUser } = useAuth();
  const [isCreateBuildListFormOpen, setIsCreateBuildListFormOpen] =
    useState(false);
  const [buildListRefreshTrigger, setBuildListRefreshTrigger] = useState(0);
  const [buildListSearchTerm, setBuildListSearchTerm] = useState('');

  const {
    data: car,
    isLoading: isLoadingCar,
    error: carApiError,
    executeRequest: fetchCar,
  } = useApiRequest(fetchCarRequestFn);

  const carTitle = car ? carFullDisplayName(car) : null;
  useDocumentMeta({
    title: carTitle ?? 'Car Generation',
    description: carTitle
      ? `Builds, parts, and modification ideas for the ${carTitle} on CarModPicker.`
      : 'Explore builds and parts for a car generation on CarModPicker.',
    canonicalPath: carId ? `/car-generations/${carId}` : undefined,
  });

  useEffect(() => {
    if (carId) {
      void fetchCar(carId);
    }
  }, [carId, fetchCar]);

  const handleBuildListCreated = () => {
    setBuildListRefreshTrigger((prev) => prev + 1);
    setIsCreateBuildListFormOpen(false);
  };

  const handleBuildListSearchChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setBuildListSearchTerm(e.target.value);
    // Reset to page 1 when search changes (handled by BuildListList component)
  };

  const openCreateBuildListDialog = () => {
    setIsCreateBuildListFormOpen(true);
  };

  if (isLoadingCar) {
    return (
      <>
        <PageHeader title="Car Details" />
        <Spinner />
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
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={`${carFullDisplayName(car)} (${formatCarYearRange(car.start_year, car.end_year)})`}
      />
      <Card>
        <div className="mb-4">
          <SectionHeader title="Car Information" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-foreground mb-6">
          <CardInfoItem label="Make:">
            <p>{car.car_make_name ?? ''}</p>
          </CardInfoItem>
          <CardInfoItem label="Model:">
            <p>{carModelDisplayName(car)}</p>
          </CardInfoItem>
          <CardInfoItem label="Generation:">
            <p>{carGenerationDisplayName(car)}</p>
          </CardInfoItem>
          <CardInfoItem label="Year Range:">
            <p>{formatCarYearRange(car.start_year, car.end_year)}</p>
          </CardInfoItem>
          {car.description && (
            <CardInfoItem label="Description:">
              <p>{car.description}</p>
            </CardInfoItem>
          )}
        </div>
      </Card>

      <Divider />

      {/* Dialog for Creating Build List */}
      <Dialog
        open={isCreateBuildListFormOpen}
        onOpenChange={setIsCreateBuildListFormOpen}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{`Create Build List for ${car.car_make_name ?? ''} ${carModelDisplayName(car)}`}</DialogTitle>
          </DialogHeader>
          <CreateBuildListForm onBuildListCreated={handleBuildListCreated} />
        </DialogContent>
      </Dialog>

      {/* Build Lists Section */}
      {currentUser && (
        <>
          <div className="mb-4">
            <SectionHeader
              title={`Build Lists for ${carFullDisplayName(car)}`}
            />
            <div className="mt-4">
              <Input
                id="search-build-lists"
                type="text"
                placeholder="Search build lists by name or description..."
                value={buildListSearchTerm}
                onChange={handleBuildListSearchChange}
                className="w-full"
              />
            </div>
          </div>
          <BuildListList
            carId={car.id}
            refreshKey={buildListRefreshTrigger}
            title=""
            emptyMessage="This car doesn't have any build lists yet."
            onAddBuildListClick={openCreateBuildListDialog}
            search={buildListSearchTerm.trim() || undefined}
          />
        </>
      )}
    </div>
  );
}

export default ViewCar;
