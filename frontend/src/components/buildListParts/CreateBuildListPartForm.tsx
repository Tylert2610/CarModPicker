import { useState, useEffect } from 'react';
import { buildListPartsApi, globalPartsApi } from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  GlobalPartCreate,
  GlobalPartRead,
  BuildListPartCreate,
} from '../../types/Api';

import Input from '../common/Input';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ErrorAlert } from '../common/Alerts';
import LoadingSpinner from '../common/LoadingSpinner';
import Card from '../common/Card';

interface CreateBuildListPartFormProps {
  buildListId: number;
  onPartAdded: () => void;
  onCancel: () => void;
}

const fetchGlobalPartsRequestFn = () => globalPartsApi.getGlobalParts();

function CreateBuildListPartForm({
  buildListId,
  onPartAdded,
  onCancel,
}: CreateBuildListPartFormProps) {
  const [mode, setMode] = useState<'create' | 'select'>('create');
  const [selectedGlobalPartId, setSelectedGlobalPartId] = useState<
    number | null
  >(null);
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    brand: '',
    description: '',
    price: '',
    image_url: '',
    category_id: 1, // Default category
    notes: '',
  });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAddingExisting, setIsAddingExisting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [addExistingError, setAddExistingError] = useState<string | null>(null);

  const {
    data: globalParts,
    isLoading: isLoadingGlobalParts,
    error: globalPartsError,
    executeRequest: fetchGlobalParts,
  } = useApiRequest(fetchGlobalPartsRequestFn);

  useEffect(() => {
    void fetchGlobalParts();
  }, [fetchGlobalParts]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === 'create') {
      if (!formData.name.trim()) {
        setValidationError('Global part name is required');
        return;
      }

      setIsCreating(true);
      setCreateError(null);

      try {
        const globalPartData: GlobalPartCreate = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          price: formData.price ? parseFloat(formData.price) : null,
          image_url: formData.image_url.trim() || null,
          category_id: formData.category_id,
          brand: formData.brand.trim() || null,
          part_number: formData.part_number.trim() || null,
        };

        const buildListPartData: BuildListPartCreate = {
          notes: formData.notes.trim() || null,
        };

        await buildListPartsApi.createGlobalPartAndAddToBuildList(
          buildListId,
          globalPartData,
          buildListPartData
        );

        onPartAdded();
      } catch (error) {
        setCreateError(
          error instanceof Error
            ? error.message
            : 'Failed to create and add part'
        );
      } finally {
        setIsCreating(false);
      }
    } else {
      if (!selectedGlobalPartId) {
        setValidationError('Please select a global part');
        return;
      }

      setIsAddingExisting(true);
      setAddExistingError(null);

      try {
        const buildListPartData: BuildListPartCreate = {
          notes: formData.notes.trim() || null,
        };

        await buildListPartsApi.addGlobalPartToBuildList(
          buildListId,
          selectedGlobalPartId,
          buildListPartData
        );

        onPartAdded();
      } catch (error) {
        setAddExistingError(
          error instanceof Error
            ? error.message
            : 'Failed to add part to build list'
        );
      } finally {
        setIsAddingExisting(false);
      }
    }
  };

  const isLoading = isCreating || isAddingExisting;

  return (
    <form
      onSubmit={(e) => {
        void handleSubmit(e);
      }}
      className="space-y-6"
    >
      {(createError || addExistingError || validationError) && (
        <ErrorAlert
          message={createError || addExistingError || validationError || ''}
        />
      )}

      {/* Mode Selection */}
      <div className="flex space-x-4 mb-6">
        <button
          type="button"
          onClick={() => setMode('create')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            mode === 'create'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          Create New Global Part
        </button>
        <button
          type="button"
          onClick={() => setMode('select')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            mode === 'select'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          Select Existing Global Part
        </button>
      </div>

      {mode === 'create' ? (
        /* Create New Global Part Form */
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">
            Create New Global Part
          </h3>

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
        </div>
      ) : (
        /* Select Existing Global Part */
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">
            Select Existing Global Part
          </h3>

          {isLoadingGlobalParts ? (
            <LoadingSpinner />
          ) : globalPartsError ? (
            <ErrorAlert message="Failed to load global parts" />
          ) : (
            <div className="max-h-64 overflow-y-auto space-y-2">
              {globalParts?.map((part: GlobalPartRead) => (
                <Card
                  key={part.id}
                  className={`cursor-pointer transition-colors ${
                    selectedGlobalPartId === part.id
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'hover:bg-gray-800'
                  }`}
                  onClick={() => setSelectedGlobalPartId(part.id)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-medium text-gray-200">{part.name}</h4>
                      {part.brand && (
                        <p className="text-sm text-gray-400">
                          Brand: {part.brand}
                        </p>
                      )}
                      {part.description && (
                        <p className="text-sm text-gray-400 mt-1">
                          {part.description}
                        </p>
                      )}
                    </div>
                    {part.price && (
                      <span className="text-sm font-medium text-green-400">
                        ${part.price}
                      </span>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Notes Field (Common to both modes) */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-200">
          Build List Notes
        </h3>
        <Input
          label="Notes (Optional)"
          id="build-list-part-notes"
          name="notes"
          type="text"
          value={formData.notes}
          onChange={handleInputChange}
          placeholder="Add notes about this part in your build list"
        />
      </div>

      <div className="flex justify-end space-x-3 pt-4">
        <SecondaryButton type="button" onClick={onCancel} disabled={isLoading}>
          Cancel
        </SecondaryButton>
        <ActionButton type="submit" disabled={isLoading}>
          {isLoading ? (
            <LoadingSpinner />
          ) : mode === 'create' ? (
            'Create & Add to Build List'
          ) : (
            'Add to Build List'
          )}
        </ActionButton>
      </div>
    </form>
  );
}

export default CreateBuildListPartForm;
