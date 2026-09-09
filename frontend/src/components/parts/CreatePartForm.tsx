import { ApiError } from '@webbpulse/api-client';
import { Link } from 'react-router-dom';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  PartCreate,
} from '../../types/Api';

import CarModelMultiSelect from '../cars/CarModelMultiSelect';
import ImageUpload from '../forms/ImageUpload';
import SearchableSelect, {
  type SearchableSelectOption,
} from '../forms/SearchableSelect';
import { ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';
import { LARGE_FETCH_LIMIT } from '../../constants';
import {
  getApiErrorCode,
  getApiErrorDetails,
  getApiErrorMessage,
} from '../../utils/apiError';

interface CreatePartFormProps {
  onPartCreated: () => void;
}

const createPartRequestFn = (partData: PartCreate) =>
  apiClient.post<PartCreate>('/parts/', partData);
const fetchCarsRequestFn = () =>
  carGenerationsApi.listCars({ limit: LARGE_FETCH_LIMIT });

function CreatePartForm({ onPartCreated }: CreatePartFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    part_number: '',
    part_manufacturer_id: null as string | null,
    description: '',
    product_url: '',
    category_id: null as string | null,
    car_ids: [] as string[],
    is_universal: false,
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [duplicatePartId, setDuplicatePartId] = useState<string | null>(null);
  const [isCheckingUrl, setIsCheckingUrl] = useState(false);
  const [cars, setCars] = useState<CarGenerationRead[]>([]);
  const [isLoadingCars, setIsLoadingCars] = useState(true);
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [part_manufacturers, setPartManufacturers] = useState<
    PartManufacturerResponse[]
  >([]);
  const [isLoadingPartManufacturers, setIsLoadingPartManufacturers] =
    useState(true);
  const [pendingPartManufacturerName, setPendingPartManufacturerName] =
    useState<string | null>(null);
  const urlCheckTimeoutRef = useRef<number | null>(null);

  // Convert categories to SearchableSelect options (only active categories)
  const categoryOptions: SearchableSelectOption[] = useMemo(() => {
    return categories
      .filter((category) => category.is_active)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((category) => ({
        id: category.id,
        label: category.display_name || category.name,
        value: category.id,
      }));
  }, [categories]);

  // Filter function for categories
  const filterCategories = useCallback(
    (
      options: SearchableSelectOption[],
      searchText: string
    ): SearchableSelectOption[] => {
      if (!searchText.trim()) return options;
      const lowerText = searchText.toLowerCase();
      return options.filter((opt) => {
        const category = categories.find((c) => c.id === opt.value);
        if (!category) return false;
        return (
          opt.label.toLowerCase().includes(lowerText) ||
          category.name.toLowerCase().includes(lowerText) ||
          (category.description &&
            category.description.toLowerCase().includes(lowerText))
        );
      });
    },
    [categories]
  );

  // Convert part_manufacturers to SearchableSelect options
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

  // Filter function for part_manufacturers
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

  const handleCategoryChange = (value: number | string | null) => {
    const categoryId = value !== null && value !== '' ? String(value) : null;
    setFormData((prev) => ({ ...prev, category_id: categoryId }));
    if (validationError) setValidationError(null);
  };

  const handlePartManufacturerChange = (value: number | string | null) => {
    const part_manufacturerId =
      value !== null && value !== '' ? String(value) : null;
    setFormData((prev) => ({
      ...prev,
      part_manufacturer_id: part_manufacturerId,
    }));
    // Clear pending part_manufacturer if an existing part_manufacturer is selected or value is cleared
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
    // Store the part_manufacturer name to be created later, don't create it yet
    setPendingPartManufacturerName(part_manufacturerName.trim());
    // Clear the part_manufacturer_id since we're creating a new part_manufacturer
    setFormData((prev) => ({ ...prev, part_manufacturer_id: null }));
    if (validationError) setValidationError(null);
  };

  const handlePartManufacturerInputChange = (text: string) => {
    // Clear pending part_manufacturer if user types something different
    if (
      pendingPartManufacturerName &&
      text.trim() !== pendingPartManufacturerName
    ) {
      setPendingPartManufacturerName(null);
    }
  };

  const { isLoading, error } = useApiRequest(createPartRequestFn);
  const [isCreating, setIsCreating] = useState(false);

  const { data: carsData, executeRequest: fetchCars } =
    useApiRequest(fetchCarsRequestFn);
  const fetchCategoriesRequestFn = () => categoriesApi.getCategories();
  const { data: categoriesData, executeRequest: fetchCategories } =
    useApiRequest(fetchCategoriesRequestFn);
  const fetchPartManufacturersRequestFn = () =>
    partManufacturersApi.getPartManufacturers(true);
  const {
    data: part_manufacturersData,
    executeRequest: fetchPartManufacturers,
  } = useApiRequest(fetchPartManufacturersRequestFn);

  useEffect(() => {
    void fetchCars();
    void fetchCategories();
    void fetchPartManufacturers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only fetch once on mount - request functions are stable

  useEffect(() => {
    if (carsData && Array.isArray(carsData)) {
      setCars(carsData);
      setIsLoadingCars(false);
    }
  }, [carsData]);

  useEffect(() => {
    if (categoriesData && Array.isArray(categoriesData)) {
      setCategories(categoriesData);
      setIsLoadingCategories(false);
    }
  }, [categoriesData]);

  useEffect(() => {
    if (part_manufacturersData && Array.isArray(part_manufacturersData)) {
      setPartManufacturers(part_manufacturersData);
      setIsLoadingPartManufacturers(false);
    }
  }, [part_manufacturersData]);

  // Debounced URL checking effect
  useEffect(() => {
    // Clear any existing timeout
    if (urlCheckTimeoutRef.current) {
      clearTimeout(urlCheckTimeoutRef.current);
    }

    const url = formData.product_url.trim();

    // Don't check if URL is empty
    if (!url) {
      setDuplicatePartId(null);
      setIsCheckingUrl(false);
      return;
    }

    // Basic URL validation - only check if it looks like a URL
    const urlPattern = /^https?:\/\/.+/;
    if (!urlPattern.test(url)) {
      setDuplicatePartId(null);
      setIsCheckingUrl(false);
      return;
    }

    // Set checking state
    setIsCheckingUrl(true);
    setDuplicatePartId(null);

    // Debounce the check - wait 500ms after user stops typing
    urlCheckTimeoutRef.current = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await partsApi.checkProductUrl(url);
          if (response.data.existing_part_id) {
            setDuplicatePartId(response.data.existing_part_id);
          } else {
            setDuplicatePartId(null);
          }
        } catch {
          // Silently fail - don't show error for URL checks
          setDuplicatePartId(null);
        } finally {
          setIsCheckingUrl(false);
        }
      })();
    }, 500);

    // Cleanup function
    return () => {
      if (urlCheckTimeoutRef.current) {
        clearTimeout(urlCheckTimeoutRef.current);
      }
    };
  }, [formData.product_url]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) setValidationError(null);
    // Don't clear duplicatePartId here - let the useEffect handle it
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setValidationError('Part name is required');
      return;
    }

    if (!formData.category_id) {
      setValidationError('Category is required');
      return;
    }

    if (!formData.part_manufacturer_id && !pendingPartManufacturerName) {
      setValidationError('Part manufacturer is required');
      return;
    }

    // Create part manufacturer first if there's a pending part_manufacturer name
    let part_manufacturerId = formData.part_manufacturer_id;
    if (pendingPartManufacturerName) {
      try {
        const part_manufacturerResult = await createPartManufacturer({
          name: pendingPartManufacturerName,
          description: null,
        });
        if (part_manufacturerResult !== null && part_manufacturerResult.id) {
          part_manufacturerId = part_manufacturerResult.id;
          // Refresh part_manufacturers list
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

    const partData: PartCreate = {
      name: formData.name.trim(),
      description: formData.description.trim() || null,
      image_urls: imageFileKey ? [imageFileKey] : null,
      product_url: formData.product_url.trim() || null,
      category_id: formData.category_id,
      is_universal: formData.is_universal,
      car_ids: formData.is_universal ? [] : formData.car_ids,
      part_manufacturer_id: part_manufacturerId!, // part_manufacturerId is guaranteed to be set at this point due to validation
      part_number: formData.part_number.trim() || null,
    };

    setIsCreating(true);
    setDuplicatePartId(null);
    setValidationError(null);

    try {
      // Call API directly to access full error response
      await partsApi.createPart(partData);
      // Clear pending part_manufacturer after successful creation
      setPendingPartManufacturerName(null);
      setIsCreating(false);
      onPartCreated();
    } catch (err) {
      setIsCreating(false);
      // Handle duplicate URL error
      if (err instanceof ApiError && err.body) {
        // `PART_ALREADY_EXISTS` is what the backend actually sends for a
        // duplicate. The other two are kept because they cost nothing and this
        // branch is the only thing standing between a duplicate and a dead-end
        // error message.
        const errorCode = getApiErrorCode(err);
        if (
          errorCode === 'PART_ALREADY_EXISTS' ||
          errorCode === 'DUPLICATE_PRODUCT_URL' ||
          errorCode === 'CONFLICT'
        ) {
          // Extract existing part ID from details or message
          const existingPartId = getApiErrorDetails(err)?.['existing_part_id'];
          if (typeof existingPartId === 'string') {
            setDuplicatePartId(existingPartId);
            setValidationError(null);
            return;
          }
          // Try to extract from message if details not available
          const message = getApiErrorMessage(err, '');
          const match = message.match(/Part ID: ([\w-]+)/);
          if (match && match[1]) {
            setDuplicatePartId(match[1]);
            setValidationError(null);
            return;
          }
        }
        // For other errors, set validation error
        setValidationError(
          getApiErrorMessage(err, 'Failed to create part. Please try again.')
        );
      } else {
        setValidationError('Failed to create part. Please try again.');
      }
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

      <div>
        <label
          htmlFor="global-part-product-url"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Product URL
        </label>
        <Input
          id="global-part-product-url"
          name="product_url"
          type="url"
          value={formData.product_url}
          onChange={handleInputChange}
          placeholder="https://example.com/product"
        />
        {isCheckingUrl && formData.product_url.trim() && (
          <p className="mt-1 text-xs text-gray-400 flex items-center gap-1">
            <Spinner inline size="xs" />
            <span>Checking if URL already exists...</span>
          </p>
        )}
        {duplicatePartId && (
          <div className="mt-2 p-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
            <div className="flex items-start gap-2">
              <svg
                className="w-4 h-4 flex-shrink-0 text-yellow-400 mt-0.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <div className="flex-grow min-w-0">
                <p className="text-sm font-medium text-yellow-300 mb-1">
                  A part with this URL already exists
                </p>
                <p className="text-xs text-yellow-200/80 mb-2">
                  This product URL is already associated with an existing part
                  in the catalog.
                </p>
                <Link
                  to={`/parts/${duplicatePartId}`}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-yellow-300 hover:text-yellow-200 underline"
                >
                  <span>View existing part</span>
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>

      <SearchableSelect
        id="global-part-category"
        name="category_id"
        label="Category *"
        placeholder="Type to search for a category..."
        value={formData.category_id}
        onChange={handleCategoryChange}
        options={categoryOptions}
        disabled={isLoadingCategories}
        isLoading={isLoadingCategories}
        emptyMessage="No categories found. Try a different search term."
        filterOptions={filterCategories}
      />

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="global-part-universal"
          checked={formData.is_universal}
          onChange={handleUniversalChange}
          className="rounded border-gray-500 bg-gray-700 text-info focus:ring-info"
        />
        <label
          htmlFor="global-part-universal"
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
        currentImageUrl={imageFileKey}
        entityType="part"
        onImageUploaded={(fileKey) => {
          setImageFileKey(fileKey);
        }}
        onImageRemoved={() => {
          setImageFileKey(null);
        }}
        label="Part Image (Optional)"
        maxSizeMB={10}
      />

      <div className="flex justify-end space-x-3 pt-4">
        <Button
          type="button"
          variant="secondary"
          onClick={() => void onPartCreated()}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading || isCreating}>
          {isLoading || isCreating ? (
            <Spinner inline size="xs" />
          ) : (
            'Create Part'
          )}
        </Button>
      </div>
    </form>
  );
}

export default CreatePartForm;
