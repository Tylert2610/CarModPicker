import React, { useState, useEffect } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { PartUpdate, PartRead } from '../../types/Api';
import Input from '../common/Input';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert, ConfirmationAlert } from '../common/Alerts';
import SecondaryButton from '../buttons/SecondaryButton';

interface EditPartFormProps {
  part: PartRead;
  onPartUpdated: (updatedPart: PartRead) => void;
  onCancel: () => void;
}

const updatePartRequestFn = (payload: { partId: number; data: PartUpdate }) =>
  apiClient.put<PartRead>(`/parts/${payload.partId}`, payload.data);

const EditPartForm: React.FC<EditPartFormProps> = ({
  part,
  onPartUpdated,
  onCancel,
}) => {
  const [name, setName] = useState(part.name);
  const [description, setDescription] = useState(part.description || '');
  const [imageUrl, setImageUrl] = useState(part.image_url || '');
  const [partNumber, setPartNumber] = useState(part.part_number || '');
  const [manufacturer, setManufacturer] = useState(part.manufacturer || '');
  const [price, setPrice] = useState<number | ''>(part.price ?? '');

  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeUpdatePart,
    setError: setApiError,
  } = useApiRequest(updatePartRequestFn);

  useEffect(() => {
    setName(part.name);
    setDescription(part.description || '');
    setImageUrl(part.image_url || '');
    setPartNumber(part.part_number || '');
    setManufacturer(part.manufacturer || '');
    setPrice(part.price ?? '');
    setApiError(null);
    setFormMessage(null);
  }, [part, setApiError]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);
    setFormMessage(null);

    if (!name.trim()) {
      setFormMessage({
        type: 'error',
        text: 'Part name is required.',
      });
      return;
    }

    const payload: PartUpdate = {
      name: name.trim(),
      description: description.trim() || null,
      image_url: imageUrl.trim() || null,
      part_number: partNumber.trim() || null,
      manufacturer: manufacturer.trim() || null,
      price: price === '' ? null : Number(price),
    };

    // Basic change detection
    let hasChanges = false;
    if (payload.name !== part.name) hasChanges = true;
    if (payload.description !== (part.description || null)) hasChanges = true;
    if (payload.image_url !== (part.image_url || null)) hasChanges = true;
    if (payload.part_number !== (part.part_number || null)) hasChanges = true;
    if (payload.manufacturer !== (part.manufacturer || null)) hasChanges = true;
    if (payload.price !== (part.price ?? null)) hasChanges = true;

    if (!hasChanges) {
      setFormMessage({ type: 'error', text: 'No changes detected.' });
      return;
    }

    const result = await executeUpdatePart({
      partId: part.id,
      data: payload,
    });

    if (result) {
      setFormMessage({
        type: 'success',
        text: 'Part updated successfully!',
      });
      onPartUpdated(result);
    }
  };

  return (
    <div className="p-1">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Part Name"
          id={`edit-part-name-${part.id}`}
          name="part-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Description (Optional)"
          id={`edit-part-description-${part.id}`}
          name="part-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Image URL (Optional)"
          id={`edit-part-image_url-${part.id}`}
          name="part-image_url"
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          disabled={isLoading}
          placeholder="https://example.com/part-image.png"
        />
        <Input
          label="Part Number (Optional)"
          id={`edit-part-part_number-${part.id}`}
          name="part_number"
          type="text"
          value={partNumber}
          onChange={(e) => setPartNumber(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Manufacturer (Optional)"
          id={`edit-part-manufacturer-${part.id}`}
          name="manufacturer"
          type="text"
          value={manufacturer}
          onChange={(e) => setManufacturer(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Price (Optional)"
          id={`edit-part-price-${part.id}`}
          name="price"
          type="number"
          value={price}
          onChange={(e) =>
            setPrice(e.target.value === '' ? '' : parseFloat(e.target.value))
          }
          disabled={isLoading}
          step="0.01"
          placeholder="e.g., 19.99"
          
        />

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

export default EditPartForm;
