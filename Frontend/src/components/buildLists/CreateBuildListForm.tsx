import React, { useState } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { BuildListCreate, BuildListRead } from '../../types/Api';
import Input from '../common/Input';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert, ConfirmationAlert } from '../common/Alerts';

interface CreateBuildListFormProps {
  carId: number;
  onBuildListCreated: (newBuildList: BuildListRead) => void;
}

const createBuildListRequestFn = (payload: BuildListCreate) =>
  apiClient.post<BuildListRead>('/build-lists/', payload);

const CreateBuildListForm: React.FC<CreateBuildListFormProps> = ({
  carId,
  onBuildListCreated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeCreateBuildList,
    setError: setApiError,
  } = useApiRequest(createBuildListRequestFn);

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

    const payload: BuildListCreate = {
      name: name.trim(),
      description: description.trim() || null,
      car_id: carId,
      image_url: imageUrl.trim() || null,
    };

    const result = await executeCreateBuildList(payload);

    if (result) {
      setFormMessage({
        type: 'success',
        text: 'Build list created successfully!',
      });
      onBuildListCreated(result);
      // Reset form
      setName('');
      setDescription('');
      setImageUrl('');
    }
  };

  return (
    
    <div className="p-1">
      {' '}
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Build List Name"
          id="buildlist-name"
          name="buildlist-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Description (Optional)"
          id="buildlist-description"
          name="buildlist-description"
          type="text" 
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Image URL (Optional)"
          id="buildlist-image_url"
          name="buildlist-image_url"
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          disabled={isLoading}
          placeholder="https://example.com/buildlist-image.png"
        />
        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        <ButtonStretch type="submit" disabled={isLoading}>
          {isLoading ? 'Creating Build List...' : 'Create Build List'}
        </ButtonStretch>
      </form>
    </div>
  );
};

export default CreateBuildListForm;
