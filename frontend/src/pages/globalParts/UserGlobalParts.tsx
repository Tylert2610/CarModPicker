import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { globalPartsApi } from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import type { GlobalPartRead } from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/Alerts';
import ActionButton from '../../components/buttons/ActionButton';
import SecondaryButton from '../../components/buttons/SecondaryButton';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';

function UserGlobalParts() {
  const { user } = useAuth();
  const [deletingPartId, setDeletingPartId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchUserGlobalPartsRequestFn = useCallback(
    (userId: number) => globalPartsApi.getGlobalPartsByUser(userId),
    []
  );

  const {
    data: globalParts,
    isLoading,
    error,
    executeRequest: fetchUserGlobalParts,
  } = useApiRequest(fetchUserGlobalPartsRequestFn);

  useEffect(() => {
    if (user) {
      void fetchUserGlobalParts(user.id);
    }
  }, [user, fetchUserGlobalParts]);

  const handleDelete = async (partId: number) => {
    setIsDeleting(true);
    try {
      await globalPartsApi.deleteGlobalPart(partId);
      // Refresh the list
      if (user) {
        await fetchUserGlobalParts(user.id);
      }
    } catch (error) {
      console.error('Failed to delete global part:', error);
    } finally {
      setIsDeleting(false);
      setDeletingPartId(null);
    }
  };

  const canDeleteGlobalPart = (globalPart: GlobalPartRead) => {
    if (!user) return false;
    return globalPart.user_id === user.id || user.is_admin || user.is_superuser;
  };

  const canEditGlobalPart = (globalPart: GlobalPartRead) => {
    if (!user) return false;
    return globalPart.user_id === user.id || user.is_admin || user.is_superuser;
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader title="Parts I Created in Global Catalog" />
        <Card>
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader title="Parts I Created in Global Catalog" />
        <ErrorAlert message="Failed to load your global parts. Please try again." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Parts I Created in Global Catalog" />

      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Global Parts I Created" />
          <Link to="/global-parts">
            <ActionButton>Browse All Global Parts</ActionButton>
          </Link>
        </div>

        {!globalParts || globalParts.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>You haven't created any global parts yet.</p>
            <p className="text-sm mt-2">
              Global parts you create will appear here and can be added to build
              lists by other users.
            </p>
            <div className="mt-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
              <h4 className="font-semibold text-gray-300 mb-2">
                🌐 About Global Parts You Create
              </h4>
              <ul className="text-sm text-gray-400 space-y-1">
                <li>
                  • <strong>Shared</strong> in the public catalog for all users
                </li>
                <li>• Other users can add them to their build lists</li>
                <li>
                  • Only <strong>you (the creator) or admins</strong> can
                  edit/delete them
                </li>
                <li>
                  • <strong>Deleting removes from all build lists</strong> - use
                  with caution!
                </li>
                <li>• These are the "master" parts in the shared catalog</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {globalParts.map((globalPart) => (
              <div
                key={globalPart.id}
                className="bg-gray-800 rounded-lg p-4 border border-gray-700"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full">
                    Global Part
                  </span>
                </div>
                <Link
                  to={`/global-parts/${globalPart.id}`}
                  className="block group"
                >
                  <div className="aspect-square mb-3">
                    <ImageWithPlaceholder
                      srcUrl={globalPart.image_url}
                      altText={globalPart.name}
                      imageClassName="w-full h-full object-cover rounded"
                      containerClassName="w-full h-full flex justify-center items-center"
                      fallbackText="No image"
                    />
                  </div>
                  <h3 className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors duration-200 mb-2">
                    {globalPart.name}
                  </h3>
                  {globalPart.brand && (
                    <p className="text-sm text-gray-400 mb-1">
                      {globalPart.brand}
                    </p>
                  )}
                  {globalPart.part_number && (
                    <p className="text-sm text-gray-400 mb-1">
                      #{globalPart.part_number}
                    </p>
                  )}
                  {globalPart.price !== null &&
                    globalPart.price !== undefined && (
                      <p className="text-sm font-medium text-green-400">
                        ${globalPart.price.toFixed(2)}
                      </p>
                    )}
                  {globalPart.description && (
                    <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                      {globalPart.description}
                    </p>
                  )}
                </Link>

                {/* Action Buttons */}
                <div className="mt-3 pt-3 border-t border-gray-700 flex space-x-2">
                  {canEditGlobalPart(globalPart) && (
                    <Link
                      to={`/global-parts/${globalPart.id}/edit`}
                      className="flex-1"
                    >
                      <SecondaryButton className="w-full text-sm">
                        Edit
                      </SecondaryButton>
                    </Link>
                  )}
                  {canDeleteGlobalPart(globalPart) && (
                    <ActionButton
                      onClick={() => setDeletingPartId(globalPart.id)}
                      className="flex-1 text-sm bg-red-600 hover:bg-red-700"
                      disabled={isDeleting}
                    >
                      Delete
                    </ActionButton>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={deletingPartId !== null}
        onClose={() => setDeletingPartId(null)}
        onConfirm={() => {
          if (deletingPartId) {
            void handleDelete(deletingPartId);
          }
        }}
        itemName={globalParts?.find((p) => p.id === deletingPartId)?.name || ''}
        itemType="global part"
        isProcessing={isDeleting}
        error={null}
      />
    </div>
  );
}

export default UserGlobalParts;
