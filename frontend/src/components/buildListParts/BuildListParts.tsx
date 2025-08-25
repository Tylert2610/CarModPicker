import React, { useState, useEffect } from 'react';
import { buildListPartsApi } from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
} from '../../types/Api';
import { useAuth } from '../../hooks/useAuth';
import BuildListPartList from './BuildListPartList';
import EditBuildListPartForm from './EditBuildListPartForm';
import SectionHeader from '../layout/SectionHeader';
import { ErrorAlert } from '../common/Alerts';
import ActionButton from '../buttons/ActionButton';

interface BuildListPartsProps {
  buildListId: number;
  canManageParts: boolean;
  refreshKey: number;
  onAddPartClick?: () => void;
  title?: string;
  emptyMessage?: string;
}

const fetchBuildListPartsRequestFn = (buildListId: number) =>
  buildListPartsApi.getBuildListParts(buildListId);

const BuildListParts: React.FC<BuildListPartsProps> = ({
  buildListId,
  canManageParts,
  refreshKey,
  onAddPartClick,
  title = 'Parts in Build List',
  emptyMessage = 'No parts added to this build list yet.',
}) => {
  const { user: currentUser } = useAuth();
  const [editingPart, setEditingPart] =
    useState<BuildListPartReadWithGlobalPart | null>(null);
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  const {
    data: buildListParts,
    isLoading,
    error,
    executeRequest: fetchBuildListParts,
  } = useApiRequest(fetchBuildListPartsRequestFn);

  useEffect(() => {
    void fetchBuildListParts(buildListId);
  }, [buildListId, refreshKey, fetchBuildListParts]);

  // Helper function to check if user can edit a specific build list part
  const canEditBuildListPart = (
    buildListPart: BuildListPartReadWithGlobalPart
  ) => {
    if (!currentUser) return false;
    return buildListPart.added_by === currentUser.id;
  };

  // Helper function to check if user can delete a specific build list part
  const canDeleteBuildListPart = (
    buildListPart: BuildListPartReadWithGlobalPart
  ) => {
    if (!currentUser) return false;
    return (
      buildListPart.added_by === currentUser.id ||
      currentUser.is_admin ||
      currentUser.is_superuser
    );
  };

  const handleEdit = (buildListPart: BuildListPartReadWithGlobalPart) => {
    if (!canEditBuildListPart(buildListPart)) {
      console.error('User not authorized to edit this build list part');
      return;
    }
    setEditingPart(buildListPart);
    setIsEditFormOpen(true);
  };

  const handleEditSubmit = async (
    _buildListPartId: number,
    data: BuildListPartUpdate
  ) => {
    try {
      setIsUpdating(true);
      await buildListPartsApi.updateBuildListPart(
        buildListId,
        editingPart!.global_part_id,
        data
      );
      // Refresh the build list parts
      await fetchBuildListParts(buildListId);
    } catch (error) {
      console.error('Failed to update build list part:', error);
      throw error;
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = (buildListPartId: number) => {
    // Find the build list part to get the global_part_id
    const buildListPart = buildListParts?.find(
      (part) => part.id === buildListPartId
    );
    if (!buildListPart) return;

    if (!canDeleteBuildListPart(buildListPart)) {
      console.error('User not authorized to delete this build list part');
      return;
    }

    void buildListPartsApi
      .removeBuildListPart(buildListId, buildListPart.global_part_id)
      .then(() => fetchBuildListParts(buildListId))
      .catch((error: unknown) => {
        console.error('Failed to remove part from build list:', error);
      });
  };

  const handleCloseEditForm = () => {
    setIsEditFormOpen(false);
    setEditingPart(null);
  };

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
          {canManageParts && onAddPartClick && (
            <ActionButton onClick={() => void onAddPartClick()}>
              Add Part
            </ActionButton>
          )}
        </div>
        <ErrorAlert message="Failed to load build list parts. Please try again." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4">
        <SectionHeader title={title} />
        {canManageParts && onAddPartClick && (
          <ActionButton onClick={() => void onAddPartClick()}>
            Add Part
          </ActionButton>
        )}
      </div>

      <BuildListPartList
        buildListParts={buildListParts || []}
        loading={isLoading}
        onEdit={handleEdit}
        onDelete={handleDelete}
        canEdit={canManageParts}
        canDelete={canManageParts}
        emptyMessage={emptyMessage}
        // Pass individual permission check functions
        canEditPart={canEditBuildListPart}
        canDeletePart={canDeleteBuildListPart}
      />

      {editingPart && (
        <EditBuildListPartForm
          buildListPart={editingPart}
          isOpen={isEditFormOpen}
          onClose={handleCloseEditForm}
          onSubmit={handleEditSubmit}
          loading={isUpdating}
        />
      )}
    </div>
  );
};

export default BuildListParts;
