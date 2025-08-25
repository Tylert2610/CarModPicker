import { useState, useEffect } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { GlobalPartRead, GlobalPartUpdate } from '../../types/Api';

import Input from '../common/Input';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';

interface EditGlobalPartFormProps {
  globalPart: GlobalPartRead;
  onGlobalPartUpdated: () => Promise<void>;
  onCancel: () => void;
}

const updateGlobalPartRequestFn = (payload: {
  globalPartId: number;
  globalPartData: GlobalPartUpdate;
}) =>
  apiClient.put<GlobalPartUpdate>(
    `/global-parts/${payload.globalPartId}`,
    payload.globalPartData
  );

function EditGlobalPartForm({
  globalPart,
  onGlobalPartUpdated,
  onCancel,
}: EditGlobalPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand: '',
    description: '',
    price: '',
    image_url: '',
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  const {
    isLoading,
    error,
    executeRequest: updateGlobalPart,
  } = useApiRequest(updateGlobalPartRequestFn);

  useEffect(() => {
    setFormData({
      name: globalPart.name ?? '',
      part_number: globalPart.part_number ?? '',
      brand: globalPart.brand ?? '',
      description: globalPart.description ?? '',
      price:
        globalPart.price !== null && globalPart.price !== undefined
          ? globalPart.price.toString()
          : '',
      image_url: globalPart.image_url ?? '',
    });
  }, [globalPart]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setValidationError('Global part name is required');
      return;
    }

    const globalPartData: GlobalPartUpdate = {
      name: formData.name.trim(),
      part_number: formData.part_number.trim() || null,
      brand: formData.brand.trim() || null,
      description: formData.description.trim() || null,
      price: formData.price ? parseFloat(formData.price) : null,
      image_url: formData.image_url.trim() || null,
    };

    const result = await updateGlobalPart({
      globalPartId: globalPart.id,
      globalPartData,
    });
    if (result !== null) {
      await onGlobalPartUpdated();
    }
  };

  return (
    <form
      onSubmit={(e) => {
        void handleSubmit(e);
      }}
      className="space-y-4"
    >
      {(error || validationError) && (
        <ErrorAlert message={error || validationError || ''} />
      )}

      <Input
        label="Global Part Name *"
        id="global-part-name"
        name="name"
        type="text"
        value={formData.name}
        onChange={handleInputChange}
        placeholder="Enter global part name"
        required
      />

      <Input
        label="Part Number"
        id="global-part-number"
        name="part_number"
        type="text"
        value={formData.part_number}
        onChange={handleInputChange}
        placeholder="Enter part number"
      />

      <Input
        label="Brand"
        id="global-part-brand"
        name="brand"
        type="text"
        value={formData.brand}
        onChange={handleInputChange}
        placeholder="Enter brand name"
      />

      <Input
        label="Description"
        id="global-part-description"
        name="description"
        type="text"
        value={formData.description}
        onChange={handleInputChange}
        placeholder="Enter global part description"
      />

      <Input
        label="Price"
        id="global-part-price"
        name="price"
        type="number"
        value={formData.price}
        onChange={handleInputChange}
        placeholder="0.00"
        step="0.01"
        min="0"
      />

      <Input
        label="Image URL"
        id="global-part-image-url"
        name="image_url"
        type="url"
        value={formData.image_url}
        onChange={handleInputChange}
        placeholder="https://example.com/image.jpg"
      />

      <div className="flex justify-end space-x-3 pt-4">
        <SecondaryButton
          type="button"
          onClick={() => void onCancel()}
          disabled={isLoading}
        >
          Cancel
        </SecondaryButton>
        <ActionButton type="submit" disabled={isLoading}>
          {isLoading ? <LoadingSpinner /> : 'Update Global Part'}
        </ActionButton>
      </div>
    </form>
  );
}

export default EditGlobalPartForm;
