import { useState, useEffect } from 'react';
import { buildListPartsApi, buildListsApi } from '../../services/Api';
import { useAuth } from '../../hooks/useAuth';
import type {
  GlobalPartReadWithVotes,
  BuildListRead,
  BuildListPartCreate,
} from '../../types/Api';

import Dialog from '../common/Dialog';
import Card from '../common/Card';
import Input from '../common/Input';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';

interface AddToBuildListDialogProps {
  isOpen: boolean;
  onClose: () => void;
  globalPart: GlobalPartReadWithVotes | null;
  onPartAdded: () => void;
}

function AddToBuildListDialog({
  isOpen,
  onClose,
  globalPart,
  onPartAdded,
}: AddToBuildListDialogProps) {
  const { user } = useAuth();
  const [selectedBuildListId, setSelectedBuildListId] = useState<number | null>(
    null
  );
  const [notes, setNotes] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildLists, setBuildLists] = useState<BuildListRead[]>([]);
  const [isLoadingBuildLists, setIsLoadingBuildLists] = useState(false);
  const [buildListsError, setBuildListsError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && user) {
      const fetchUserBuildLists = async () => {
        try {
          setIsLoadingBuildLists(true);
          const response = await buildListsApi.getBuildListsByUser(user.id);
          setBuildLists(response.data);
        } catch (error) {
          console.error('Failed to load build lists:', error);
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
      setSelectedBuildListId(null);
      setNotes('');
      setError(null);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!globalPart || !selectedBuildListId) {
      setError('Please select a build list');
      return;
    }

    setIsAdding(true);
    setError(null);

    try {
      const buildListPartData: BuildListPartCreate = {
        notes: notes.trim() || null,
      };

      await buildListPartsApi.addGlobalPartToBuildList(
        selectedBuildListId,
        globalPart.id,
        buildListPartData
      );

      onPartAdded();
      onClose();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : 'Failed to add part to build list'
      );
    } finally {
      setIsAdding(false);
    }
  };

  if (!globalPart) {
    return null;
  }

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={`Add ${globalPart.name} to Build List`}
    >
      <form
        onSubmit={(e) => {
          void handleSubmit(e);
        }}
        className="space-y-6"
      >
        {error && <ErrorAlert message={error} />}

        {/* Global Part Preview */}
        <Card>
          <div className="mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full">
                Global Part
              </span>
            </div>
            <p className="text-sm text-gray-400">
              This will create a personal copy in your build list that you can
              customize.
            </p>
          </div>
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <ImageWithPlaceholder
                srcUrl={globalPart.image_url}
                altText={globalPart.name}
                imageClassName="w-24 h-24 object-cover rounded-lg"
                containerClassName="w-24 h-24 flex justify-center items-center"
                fallbackText="No image"
              />
            </div>
            <div className="flex-grow">
              <h3 className="text-lg font-semibold text-white mb-2">
                {globalPart.name}
              </h3>
              {globalPart.brand && (
                <p className="text-sm text-gray-400 mb-1">{globalPart.brand}</p>
              )}
              {globalPart.price !== null && globalPart.price !== undefined && (
                <p className="text-sm font-medium text-green-400">
                  ${globalPart.price.toFixed(2)}
                </p>
              )}
              {globalPart.description && (
                <p className="text-sm text-gray-400 mt-2">
                  {globalPart.description}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Build List Selection */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200">
            Select Build List
          </h3>

          {isLoadingBuildLists ? (
            <LoadingSpinner />
          ) : buildListsError ? (
            <ErrorAlert message="Failed to load build lists" />
          ) : buildLists && buildLists.length > 0 ? (
            <div className="max-h-64 overflow-y-auto space-y-2">
              {buildLists.map((buildList: BuildListRead) => (
                <Card
                  key={buildList.id}
                  className={`cursor-pointer transition-colors ${
                    selectedBuildListId === buildList.id
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'hover:bg-gray-800'
                  }`}
                  onClick={() => setSelectedBuildListId(buildList.id)}
                >
                  <div>
                    <h4 className="font-medium text-gray-200">
                      {buildList.name}
                    </h4>
                    {buildList.description && (
                      <p className="text-sm text-gray-400 mt-1">
                        {buildList.description}
                      </p>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-4 text-gray-400">
              <p>No build lists found.</p>
              <p className="text-sm mt-1">
                Create a build list first to add parts to it.
              </p>
            </div>
          )}
        </div>

        {/* Notes Field */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200">
            📝 Build List Notes (Optional)
          </h3>
          <p className="text-sm text-gray-400">
            Add personal notes to your build list copy. These notes are only
            visible to you.
          </p>
          <Input
            label="Notes"
            id="build-list-notes"
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes about this part in your build list"
          />
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <SecondaryButton type="button" onClick={onClose} disabled={isAdding}>
            Cancel
          </SecondaryButton>
          <ActionButton
            type="submit"
            disabled={isAdding || !selectedBuildListId}
          >
            {isAdding ? <LoadingSpinner /> : 'Add to Build List'}
          </ActionButton>
        </div>
      </form>
    </Dialog>
  );
}

export default AddToBuildListDialog;
