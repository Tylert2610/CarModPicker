import React, { useState, useEffect } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { BuildListUpdate, BuildListRead } from '../../types/Api';
import Input from '../common/Input';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert, ConfirmationAlert } from '../common/Alerts';
import SecondaryButton from '../buttons/SecondaryButton';

interface EditBuildListFormProps {
  buildList: BuildListRead;
  onBuildListUpdated: (updatedBuildList: BuildListRead) => void;
  onCancel: () => void;
}

const updateBuildListRequestFn = (payload: {
  buildListId: number;
  data: BuildListUpdate;
}) =>
  apiClient.put<BuildListRead>(
    `/build-lists/${payload.buildListId}`,
    payload.data
  );

const EditBuildListForm: React.FC<EditBuildListFormProps> = ({
  buildList,
  onBuildListUpdated,
  onCancel,
}) => {
  const [name, setName] = useState(buildList.name);
  const [description, setDescription] = useState(buildList.description || '');
  const [imageUrl, setImageUrl] = useState(buildList.image_url || '');
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeUpdateBuildList,
    setError: setApiError,
  } = useApiRequest(updateBuildListRequestFn);

  useEffect(() => {
    setName(buildList.name);
    setDescription(buildList.description || '');
    setImageUrl(buildList.image_url || '');
    setApiError(null);
    setFormMessage(null);
  }, [buildList, setApiError]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);
    setFormMessage(null);

    if (!name.trim()) {
      setFormMessage({
        type: 'error',
        text: 'Build list name is required.',
      });
      return;
    }

    const payload: BuildListUpdate = {
      name: name.trim(),
      description: description.trim() || null,
      image_url: imageUrl.trim() || null,
     
    };

    // Always submit the data, even if no changes detected
    // This provides better UX and allows users to "save" without making changes

    const result = await executeUpdateBuildList({
      buildListId: buildList.id,
      data: payload,
    });

    if (result) {
      setFormMessage({
        type: 'success',
        text: 'Build list updated successfully!',
      });
      onBuildListUpdated(result);
    }
  };

  return (
    <div className="p-4">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        <div>
          <label htmlFor="edit-buildlist-name" className="block text-sm font-medium text-neutral-300 mb-2">
            Build List Name
          </label>
          <Input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={isLoading}
          />
        </div>
        <div>
          <label htmlFor="edit-buildlist-description" className="block text-sm font-medium text-neutral-300 mb-2">
            Description (Optional)
          </label>
          <Input
            type="text" 
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isLoading}
          />
        </div>
        <div>
          <label htmlFor="edit-buildlist-image_url" className="block text-sm font-medium text-neutral-300 mb-2">
            Image URL (Optional)
          </label>
          <Input
            type="url"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            disabled={isLoading}
            placeholder="https://example.com/buildlist-image.png"
          />
        </div>
        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        <div className="flex space-x-2 pt-2">
          <ButtonStretch type="submit" disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save Changes'}
          </ButtonStretch>
          <SecondaryButton
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="w-full"
          >
            Cancel
          </SecondaryButton>
        </div>
      </form>
    </div>
  );
};

export default EditBuildListForm;
