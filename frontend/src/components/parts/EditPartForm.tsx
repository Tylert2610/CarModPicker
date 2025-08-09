import { useState, useEffect } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { PartRead, PartUpdate } from '../../types/Api';

import Input from '../common/Input';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';

interface EditPartFormProps {
  part: PartRead;
  onPartUpdated: () => Promise<void>;
  onCancel: () => void;
}

const updatePartRequestFn = (payload: { partId: number; partData: PartUpdate }) =>
  apiClient.put<PartUpdate>(`/parts/${payload.partId}`, payload.partData);

function EditPartForm({ part, onPartUpdated, onCancel }: EditPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_type: '',
    part_number: '',
    manufacturer: '',
    description: '',
    price: '',
    image_url: '',
  });

  const {
    isLoading,
    error,
    executeRequest: updatePart,
    setError,
  } = useApiRequest(updatePartRequestFn);

  useEffect(() => {
    setFormData({
      name: part.name || '',
      part_type: part.part_type || '',
      part_number: part.part_number || '',
      manufacturer: part.manufacturer || '',
      description: part.description || '',
      price: part.price !== null && part.price !== undefined ? part.price.toString() : '',
      image_url: part.image_url || '',
    });
  }, [part]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (error) setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setError('Part name is required');
      return;
    }

    const partData: PartUpdate = {
      name: formData.name.trim(),
      part_type: formData.part_type.trim() || null,
      part_number: formData.part_number.trim() || null,
      manufacturer: formData.manufacturer.trim() || null,
      description: formData.description.trim() || null,
      price: formData.price ? parseFloat(formData.price) : null,
      image_url: formData.image_url.trim() || null,
    };

    const result = await updatePart({ partId: part.id, partData });
    if (result !== null) {
      await onPartUpdated();
    }
  };

  return (
    <form
      onSubmit={(e) => {
        
        void handleSubmit(e);
      }}
      className="space-y-4"
    >
      {error && <ErrorAlert message={error} />}

      <Input
        label="Part Name *"
        id="part-name"
        name="name"
        type="text"
        value={formData.name}
        onChange={handleInputChange}
        placeholder="Enter part name"
        required
      />

      <Input
        label="Part Type"
        id="part-type"
        name="part_type"
        type="text"
        value={formData.part_type}
        onChange={handleInputChange}
        placeholder="e.g., Exhaust, Intake, Suspension"
      />

      <Input
        label="Part Number"
        id="part-number"
        name="part_number"
        type="text"
        value={formData.part_number}
        onChange={handleInputChange}
        placeholder="Enter part number"
      />

      <Input
        label="Manufacturer"
        id="part-manufacturer"
        name="manufacturer"
        type="text"
        value={formData.manufacturer}
        onChange={handleInputChange}
        placeholder="Enter manufacturer name"
      />

      <Input
        label="Description"
        id="part-description"
        name="description"
        type="text"
        value={formData.description}
        onChange={handleInputChange}
        placeholder="Enter part description"
      />

      <Input
        label="Price"
        id="part-price"
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
        id="part-image-url"
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
          {isLoading ? <LoadingSpinner /> : 'Update Part'}
        </ActionButton>
      </div>
    </form>
  );
}

export default EditPartForm;
