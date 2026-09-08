import React, { useCallback, useEffect, useState } from 'react';
import { LARGE_FETCH_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { carGenerationsApi } from '../../api/car_generations';
import { apiClient } from '../../api/client';
import {
  carFullDisplayName,
  carGenerationDisplayName,
  formatCarYearRange,
  normalizeCarReadList,
} from '../../utils/carUtils';
import type {
  BuildListCreate,
  BuildListRead,
  CarGenerationRead,
} from '../../types/Api';
import ImageUpload from '../forms/ImageUpload';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

interface CreateBuildListFormProps {
  onBuildListCreated: (newBuildList: BuildListRead) => void;
}

const createBuildListRequestFn = (payload: BuildListCreate) =>
  apiClient.post<BuildListRead>('/build-lists/', payload);

const CreateBuildListForm: React.FC<CreateBuildListFormProps> = ({
  onBuildListCreated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [basePriceDollars, setBasePriceDollars] = useState<string>('');
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [selectedMake, setSelectedMake] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedGeneration, setSelectedGeneration] =
    useState<CarGenerationRead | null>(null);
  const [availableMakes, setAvailableMakes] = useState<string[]>([]);
  const [availableCars, setAvailableCars] = useState<CarGenerationRead[]>([]);
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

  // Memoize request functions to prevent infinite re-renders
  const fetchMakeStatsFn = useCallback(
    () => carGenerationsApi.getCarMakeStats(),
    []
  );

  // Fetch available manufacturers
  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  // Memoize cars by make request function
  const fetchCarsByMakeFn = useCallback(
    (make: string) =>
      carGenerationsApi.getCarsByMake(make, { limit: LARGE_FETCH_LIMIT }),
    []
  );

  // Fetch cars by make when make is selected
  const {
    data: carsByMake,
    isLoading: isLoadingCars,
    executeRequest: fetchCarsByMake,
  } = useApiRequest(fetchCarsByMakeFn);

  useEffect(() => {
    void fetchMakes();
  }, [fetchMakes]);

  useEffect(() => {
    if (makeStats) {
      const makes = Object.keys(makeStats).sort();
      setAvailableMakes(makes);
    }
  }, [makeStats]);

  useEffect(() => {
    if (selectedMake) {
      void fetchCarsByMake(selectedMake);
      setSelectedModel(''); // Reset model when make changes
      setSelectedGeneration(null); // Reset generation when make changes
    } else {
      setAvailableCars([]);
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [selectedMake, fetchCarsByMake]);

  useEffect(() => {
    setAvailableCars(normalizeCarReadList(carsByMake ?? undefined));
  }, [carsByMake]);

  useEffect(() => {
    // Reset generation when model changes
    if (selectedModel) {
      setSelectedGeneration(null);
    }
  }, [selectedModel]);

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

    if (!selectedGeneration) {
      setFormMessage({
        type: 'error',
        text: 'Please select a car generation.',
      });
      return;
    }

    const trimmedBasePrice = basePriceDollars.trim();
    const parsedBaseDollars =
      trimmedBasePrice === '' ? 0 : Number(trimmedBasePrice);
    if (!Number.isFinite(parsedBaseDollars) || parsedBaseDollars < 0) {
      setFormMessage({
        type: 'error',
        text: 'Base car price must be a non-negative number.',
      });
      return;
    }
    const basePriceCents = Math.round(parsedBaseDollars * 100);

    const payload: BuildListCreate = {
      name: name.trim(),
      description: description.trim() || null,
      car_id: selectedGeneration.id,
      image_urls: imageFileKey ? [imageFileKey] : null,
      base_price_cents: basePriceCents,
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
      setBasePriceDollars('');
      setImageFileKey(null);
      setSelectedMake('');
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  };

  // Get unique models for selected make
  const uniqueModels = Array.from(
    new Set(
      availableCars.map((car) => car.car_model_name ?? '').filter(Boolean)
    )
  ).sort();

  // Get generations (cars) for selected make and model
  const generations = availableCars
    .filter(
      (car) =>
        (car.car_make_name ?? '') === selectedMake &&
        (car.car_model_name ?? '') === selectedModel
    )
    .sort((a, b) => {
      // Sort by start_year, then generation_name
      if (a.start_year !== b.start_year) {
        return a.start_year - b.start_year;
      }
      return a.generation_name.localeCompare(b.generation_name);
    });

  return (
    <div className="p-2">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        {/* Car Selection Section */}
        <div className="space-y-2">
          <h3 className="text-lg font-semibold text-gray-200">Select Car</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Make
              </label>
              <Select
                value={selectedMake || ''}
                onValueChange={(v) => setSelectedMake(v)}
                disabled={isLoadingMakes}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={isLoadingMakes ? 'Loading…' : 'Select make'}
                  />
                </SelectTrigger>
                <SelectContent>
                  {availableMakes.map((make) => (
                    <SelectItem key={make} value={make}>
                      {make}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Model
              </label>
              <Select
                value={selectedModel || ''}
                onValueChange={(v) => setSelectedModel(v)}
                disabled={!selectedMake || isLoadingCars}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      !selectedMake
                        ? 'Select make first'
                        : isLoadingCars
                          ? 'Loading…'
                          : 'Select model'
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {uniqueModels.map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Generation
              </label>
              <Select
                value={selectedGeneration ? String(selectedGeneration.id) : ''}
                onValueChange={(v) => {
                  const gen =
                    generations.find((g) => String(g.id) === v) ?? null;
                  setSelectedGeneration(gen);
                }}
                disabled={!selectedModel}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={
                      !selectedModel
                        ? 'Select model first'
                        : 'Select generation'
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {generations.map((car) => (
                    <SelectItem key={car.id} value={String(car.id)}>
                      {carGenerationDisplayName(car)} (
                      {formatCarYearRange(car.start_year, car.end_year)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {selectedGeneration && (
            <p className="text-sm text-gray-400 pt-1">
              Selected: {carFullDisplayName(selectedGeneration)}
            </p>
          )}
        </div>

        {/* Build List Details Section - Only show after car is selected */}
        {selectedGeneration && (
          <div className="space-y-4 border-t border-gray-700 pt-4">
            <h3 className="text-lg font-semibold text-gray-200">
              Build List Details
            </h3>
            <div>
              <label
                htmlFor="buildlist-name"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Build List Name
              </label>
              <Input
                id="buildlist-name"
                name="buildlist-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            <div>
              <label
                htmlFor="buildlist-description"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Description (Optional)
              </label>
              <Input
                id="buildlist-description"
                name="buildlist-description"
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isLoading}
              />
            </div>
            <div>
              <label
                htmlFor="buildlist-base-price"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Base Car Price (Optional)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                  $
                </span>
                <Input
                  id="buildlist-base-price"
                  name="buildlist-base-price"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={basePriceDollars}
                  onChange={(e) => setBasePriceDollars(e.target.value)}
                  disabled={isLoading}
                  placeholder="0.00"
                  className="pl-7"
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Purchase price of the donor car. Included in the build's total
                cost.
              </p>
            </div>
            <ImageUpload
              currentImageUrl={imageFileKey}
              entityType="build_list"
              onImageUploaded={(fileKey) => {
                setImageFileKey(fileKey);
              }}
              onImageRemoved={() => {
                setImageFileKey(null);
              }}
              label="Build List Image (Optional)"
              maxSizeMB={10}
            />
          </div>
        )}

        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        {selectedGeneration && (
          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? 'Creating Build List...' : 'Create Build List'}
          </Button>
        )}
      </form>
    </div>
  );
};

export default CreateBuildListForm;
