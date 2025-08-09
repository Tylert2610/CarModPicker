import { useState } from 'react';

import PageHeader from '../../components/layout/PageHeader';

import CarList from '../../components/cars/CarList';
import CreateCarForm from '../../components/cars/CreateCarForm';
import { useAuth } from '../../contexts/AuthContext';
import Dialog from '../../components/common/Dialog'; 

function Builder() {
  const { user } = useAuth();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isCreateCarFormOpen, setIsCreateCarFormOpen] = useState(false); 

  const handleCarCreated = () => {
    setRefreshTrigger((prev) => prev + 1);
    setIsCreateCarFormOpen(false); 
  };

  const openCreateCarDialog = () => {
    setIsCreateCarFormOpen(true);
  };

  const closeCreateCarDialog = () => {
    setIsCreateCarFormOpen(false);
  };

  return (
    <div>
      <PageHeader
        title="Builder"
        subtitle="Manage your cars and build lists."
      />

      <Dialog
        isOpen={isCreateCarFormOpen}
        onClose={closeCreateCarDialog}
        title="Add a New Car"
      >
        <CreateCarForm onCarCreated={handleCarCreated} />
      </Dialog>

      <CarList
        userId={user?.id}
        refreshKey={refreshTrigger}
        title="Your Garage"
        emptyMessage="You haven't added any cars yet. Add one above to get started!"
        onAddCarClick={openCreateCarDialog} 
        showAddCarTile={true} 
      />
      
    </div>
  );
}
export default Builder;
