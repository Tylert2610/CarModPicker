import { useCallback, useEffect, useMemo, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { carGenerationsApi } from '../../api/car_generations';
import { categoriesApi } from '../../api/categories';
import { apiClient } from '../../api/client';
import { partManufacturersApi } from '../../api/part_manufacturers';
import { partsApi } from '../../api/parts';
import type {
  PartManufacturerCreate,
  PartManufacturerResponse,
  CarGenerationRead,
  CategoryResponse,
  PartRead,
  PartUpdate,
} from '../../types/Api';

import { LARGE_FETCH_LIMIT } from '../../constants';
import CarModelMultiSelect from '../cars/CarModelMultiSelect';
import ImageUpload from '../forms/ImageUpload';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../forms/SearchableSelect';
import { ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';

interface EditPartFormProps {
  part: PartRead;
  onPartUpdated: () => Promise<void>;
  onCancel: () => void;
}

const updatePartRequestFn = (payload: {
  partId: string;
  partData: PartUpdate;
}) => apiClient.put<PartUpdate>(`/parts/${payload.partId}`, payload.partData);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();
const fetchCarsRequestFn = () =>
  carGenerationsApi.listCars({ limit: LARGE_FETCH_LIMIT });
const fetchPartManufacturersRequestFn = () =>
  partManufacturersApi.getPartManufacturers(true);

/** Edits an existing part's details, fitment, and images. */
function EditPartForm({ part, onPartUpdated, onCancel }: EditPartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    part_manufacturer_id: null as string | null,
    description: '',
    category_id: '',
    car_ids: [] as string[],
    is_universal: false,
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [cars, setCars] = useState<CarGenerationRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);
  const [part_manufacturers, setPartManufacturers] = useState<
    PartManufacturerResponse[]
  >([]);
  const [isLoadingPartManufacturers, setIsLoadingPartManufacturers] =
    useState(true);
  const [pendingPartManufacturerName, setPendingPartManufacturerName] =
    useState<string | null>(null);

  const {
    isLoading,
    error,
    executeRequest: updatePart,
  } = useApiRequest(updatePartRequestFn);

  const { data: categoriesData, executeRequest: fetchCategories } =
    useApiRequest(fetchCategoriesRequestFn);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);
  const {
    data: part_manufacturersData,
    executeRequest: fetchPartManufacturers,
  } = useApiRequest(fetchPartManufacturersRequestFn);

  useEffect(() => {
    void fetchCategories();
    void fetchCars();
    void fetchPartManufacturers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (categoriesData && Array.isArray(categoriesData)) {
      setCategories(categoriesData);
      setIsLoadingCategories(false);
    }
  }, [categoriesData]);

  useEffect(() => {
    if (carsData && Array.isArray(carsData)) {
      setCars(carsData);
      setIsLoadingCars(false);
    }
  }, [carsData]);

  useEffect(() => {
    if (part_manufacturersData && Array.isArray(part_manufacturersData)) {
      setPartManufacturers(part_manufacturersData);
      setIsLoadingPartManufacturers(false);
    }
  }, [part_manufacturersData]);

  useEffect(() => {
    try {
      const carIds = part.car_ids ?? [];
      setFormData({
        name: part.name ?? '',
        part_number: part.part_number ?? '',
        part_manufacturer_id: part.part_manufacturer_id ?? null,
        description: part.description ?? '',
        category_id: part.category_id ?? '',
        car_ids: [...carIds],
        is_universal: part.is_universal ?? false,
      });
      setImageFileKey(null);
      setImageChanged(false);
    } catch {
      setValidationError('Failed to load part data. Please refresh the page.');
    }
  }, [part]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const categoryId = e.target.value || '';
    setFormData((prev) => ({
      ...prev,
      category_id: categoryId,
    }));
    if (validationError) setValidationError(null);
  };

  const handleCarIdsChange = (carIds: string[]) => {
    setFormData((prev) => ({ ...prev, car_ids: carIds }));
    if (validationError) setValidationError(null);
  };

  const handleUniversalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setFormData((prev) => ({ ...prev, is_universal: checked }));
    if (validationError) setValidationError(null);
  };

  const handlePartManufacturerChange = (value: number | string | null) => {
    const part_manufacturerId =
      value !== null && value !== '' ? String(value) : null;
    setFormData((prev) => ({
      ...prev,
      part_manufacturer_id: part_manufacturerId,
    }));
    if (part_manufacturerId !== null || value === null) {
      setPendingPartManufacturerName(null);
    }
    if (validationError) setValidationError(null);
  };

  const createPartManufacturerRequestFn = (data: PartManufacturerCreate) =>
    partManufacturersApi.createPartManufacturer(data);
  const { executeRequest: createPartManufacturer } = useApiRequest(
    createPartManufacturerRequestFn
  );

  const handleCreateNewPartManufacturer = (part_manufacturerName: string) => {
    setPendingPartManufacturerName(part_manufacturerName.trim());
    setFormData((prev) => ({ ...prev, part_manufacturer_id: null }));
    if (validationError) setValidationError(null);
  };

  const handlePartManufacturerInputChange = (text: string) => {
    if (
      pendingPartManufacturerName &&
      text.trim() !== pendingPartManufacturerName
    ) {
      setPendingPartManufacturerName(null);
    }
  };

  const part_manufacturerOptions: SearchableSelectOption[] = useMemo(() => {
    return part_manufacturers
      .filter((part_manufacturer) => part_manufacturer.is_active)
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((part_manufacturer) => ({
        id: part_manufacturer.id,
        label: part_manufacturer.name,
        value: part_manufacturer.id,
      }));
  }, [part_manufacturers]);

  const filterPartManufacturers = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((opt) => {
        const part_manufacturer = part_manufacturers.find(
          (b) => b.id === opt.value
        );
        if (!part_manufacturer) return false;
        return (
          opt.label.toLowerCase().includes(lowerText) ||
          (part_manufacturer.description &&
            part_manufacturer.description.toLowerCase().includes(lowerText))
        );
      });
    },
    [part_manufacturers]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setValidationError('Part name is required');
      return;
    }

    if (!formData.part_manufacturer_id && !pendingPartManufacturerName) {
      setValidationError('Part manufacturer is required');
      return;
    }

    let part_manufacturerId = formData.part_manufacturer_id;
    if (pendingPartManufacturerName) {
      try {
        const part_manufacturerResult = await createPartManufacturer({
          name: pendingPartManufacturerName,
          description: null,
        });
        if (part_manufacturerResult !== null && part_manufacturerResult.id) {
          part_manufacturerId = part_manufacturerResult.id;
          await fetchPartManufacturers();
        } else {
          setValidationError(
            'Failed to create part manufacturer. Please try again.'
          );
          return;
        }
      } catch (error) {
        setValidationError(
          error instanceof Error
            ? error.message
            : 'Failed to create part manufacturer. Please try again.'
        );
        return;
      }
    }

    const partData: PartUpdate = {
      name: formData.name.trim(),
      part_number: formData.part_number.trim() || null,
      part_manufacturer_id: part_manufacturerId!,
      description: formData.description.trim() || null,
      category_id: formData.category_id,
      is_universal: formData.is_universal,
      car_ids: formData.is_universal ? [] : formData.car_ids,
    };

    const result = await updatePart({
      partId: part.id,
      partData,
    });
    if (result !== null) {
      if (imageChanged) {
        if (imageFileKey) {
          await partsApi.appendPartImages(part.id, [imageFileKey]);
        } else {
          await partsApi.removePartImage(part.id, 0);
        }
      }
      setPendingPartManufacturerName(null);
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
      {(error || validationError) && (
        <ErrorAlert message={error || validationError || ''} />
      )}

      <div>
        <label
          htmlFor="global-part-name"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Part Name *
        </label>
        <Input
          id="global-part-name"
          name="name"
          type="text"
          value={formData.name}
          onChange={handleInputChange}
          placeholder="Enter part name"
          required
        />
      </div>

      <div className="relative">
        <label
          htmlFor="global-part-category"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Category *
        </label>
        <select
          id="global-part-category"
          name="category_id"
          value={formData.category_id}
          onChange={handleCategoryChange}
          disabled={isLoadingCategories}
          required
          className="w-full px-5 py-3 bg-gray-800 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-300 ease-out min-h-[44px] [&>option]:bg-gray-800 [&>option]:text-white"
        >
          {isLoadingCategories ? (
            <option>Loading categories...</option>
          ) : (
            categories
              .filter((category) => category.is_active)
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((category) => (
                <option key={category.id} value={category.id}>
                  {category.display_name}
                </option>
              ))
          )}
        </select>
      </div>

      <div>
        <label
          htmlFor="global-part-number"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Part Number
        </label>
        <Input
          id="global-part-number"
          name="part_number"
          type="text"
          value={formData.part_number}
          onChange={handleInputChange}
          placeholder="Enter part number"
        />
      </div>

      <div>
        <SearchableSelect
          id="global-part-part_manufacturer"
          name="part_manufacturer_id"
          label="Part Manufacturer *"
          placeholder="Type to search for a part manufacturer or create new..."
          value={formData.part_manufacturer_id}
          onChange={handlePartManufacturerChange}
          options={part_manufacturerOptions}
          disabled={isLoadingPartManufacturers}
          isLoading={isLoadingPartManufacturers}
          emptyMessage="No part manufacturers found. Type a name to create a new part manufacturer."
          filterOptions={filterPartManufacturers}
          onCreateNew={handleCreateNewPartManufacturer}
          createNewLabel="Create part manufacturer"
          displayValue={pendingPartManufacturerName}
          onInputChange={handlePartManufacturerInputChange}
        />
        {pendingPartManufacturerName && (
          <div className="mt-2 px-3 py-2 bg-blue-500/20 border border-blue-500/50 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-blue-300">
              <svg
                className="w-4 h-4 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>
                New part manufacturer{' '}
                <strong>&quot;{pendingPartManufacturerName}&quot;</strong> will
                be created when you submit this form.
              </span>
            </div>
          </div>
        )}
      </div>

      <div>
        <label
          htmlFor="global-part-description"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Description
        </label>
        <Input
          id="global-part-description"
          name="description"
          type="text"
          value={formData.description}
          onChange={handleInputChange}
          placeholder="Enter part description"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="global-part-universal-edit"
          checked={formData.is_universal}
          onChange={handleUniversalChange}
          className="rounded border-gray-500 bg-gray-700 text-info focus:ring-info"
        />
        <label
          htmlFor="global-part-universal-edit"
          className="text-sm text-gray-300"
        >
          Universal part (fits all vehicles)
        </label>
      </div>
      {!formData.is_universal && (
        <CarModelMultiSelect
          cars={cars}
          value={formData.car_ids}
          onChange={handleCarIdsChange}
          label="Car models (optional)"
          placeholder="Type to search for a car model..."
          isLoading={isLoadingCars}
          emptyMessage="No cars found or all selected."
        />
      )}

      <ImageUpload
        currentImageUrl={part.image_urls?.[0] ?? null}
        entityType="part"
        entityId={part.id}
        onImageUploaded={(fileKey) => {
          setImageFileKey(fileKey);
          setImageChanged(true);
        }}
        onImageRemoved={() => {
          setImageFileKey(null);
          setImageChanged(true);
        }}
        label="Part Image (Optional)"
        maxSizeMB={10}
      />

      <div className="flex justify-end space-x-3 pt-4">
        <Button
          type="button"
          variant="secondary"
          onClick={() => void onCancel()}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? <Spinner inline size="xs" /> : 'Update Part'}
        </Button>
      </div>
    </form>
  );
}

export default EditPartForm;
