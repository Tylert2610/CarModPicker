import { useState } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { GlobalPartCreate } from '../../types/Api';

import Input from '../common/Input';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';

interface CreateGlobalPartFormProps {
  onGlobalPartCreated: () => void;
}

const createGlobalPartRequestFn = (globalPartData: GlobalPartCreate) =>
  apiClient.post<GlobalPartCreate>('/global-parts/', globalPartData);

function CreateGlobalPartForm({
  onGlobalPartCreated,
}: CreateGlobalPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand: '',
    description: '',
    price: '',
    image_url: '',
    category_id: 1, // Default category
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  const {
    isLoading,
    error,
    executeRequest: createGlobalPart,
  } = useApiRequest(createGlobalPartRequestFn);

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

    const globalPartData: GlobalPartCreate = {
      name: formData.name.trim(),
      description: formData.description.trim() || null,
      price: formData.price ? parseFloat(formData.price) : null,
      image_url: formData.image_url.trim() || null,
      category_id: formData.category_id,
      brand: formData.brand.trim() || null,
      part_number: formData.part_number.trim() || null,
    };

    const result = await createGlobalPart(globalPartData);
    if (result !== null) {
      onGlobalPartCreated();
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
          onClick={() => void onGlobalPartCreated()}
          disabled={isLoading}
        >
          Cancel
        </SecondaryButton>
        <ActionButton type="submit" disabled={isLoading}>
          {isLoading ? <LoadingSpinner /> : 'Create Global Part'}
        </ActionButton>
      </div>
    </form>
  );
}

export default CreateGlobalPartForm;
