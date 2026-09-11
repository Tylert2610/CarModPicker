import React, { useCallback, useEffect, useState } from 'react';
import { LARGE_FETCH_LIMIT } from '../../constants';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListsApi } from '../../api/build_lists';
import { carGenerationsApi } from '../../api/car_generations';
import { apiClient } from '../../api/client';
import {
  carFullDisplayName,
  carGenerationDisplayName,
  formatCarYearRange,
  normalizeCarRead,
  normalizeCarReadList,
} from '../../utils/carUtils';
import type {
  BuildListRead,
  BuildListUpdate,
  CarGenerationRead,
} from '../../types/Api';
import ImageUpload from '../forms/ImageUpload';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';

interface EditBuildListFormProps {
  buildList: BuildListRead;
  onBuildListUpdated: (updatedBuildList: BuildListRead) => void;
  onCancel: () => void;
}

const updateBuildListRequestFn = (payload: {
  buildListId: string;
  data: BuildListUpdate;
}) =>
  apiClient.put<BuildListRead>(
    `/build-lists/${payload.buildListId}`,
    payload.data
  );

/** Edits a build list's details and its vehicle assignment. */
const EditBuildListForm: React.FC<EditBuildListFormProps> = ({
  buildList,
  onBuildListUpdated,
  onCancel,
}) => {
  const [name, setName] = useState(buildList.name);
  const [description, setDescription] = useState(buildList.description || '');
  const [basePriceDollars, setBasePriceDollars] = useState<string>(
    buildList.base_price_cents
      ? (buildList.base_price_cents / 100).toFixed(2)
      : ''
  );
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
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
    executeRequest: executeUpdateBuildList,
    setError: setApiError,
  } = useApiRequest(updateBuildListRequestFn);

  const fetchMakeStatsFn = useCallback(
    () => carGenerationsApi.getCarMakeStats(),
    []
  );

  const {
    data: makeStats,
    isLoading: isLoadingMakes,
    executeRequest: fetchMakes,
  } = useApiRequest(fetchMakeStatsFn);

  const fetchCarsByMakeFn = useCallback(
    (make: string) =>
      carGenerationsApi.getCarsByMake(make, { limit: LARGE_FETCH_LIMIT }),
    []
  );

  const {
    data: carsByMake,
    isLoading: isLoadingCars,
    executeRequest: fetchCarsByMake,
  } = useApiRequest(fetchCarsByMakeFn);

  const fetchCurrentCarFn = useCallback(
    (carId: string) => carGenerationsApi.getCar(carId),
    []
  );

  const { data: currentCarData, executeRequest: fetchCurrentCar } =
    useApiRequest(fetchCurrentCarFn);

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
      setSelectedModel('');
      setSelectedGeneration(null);
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
    if (selectedModel) {
      setSelectedGeneration(null);
    }
  }, [selectedModel]);

  useEffect(() => {
    if (buildList.car_id) {
      void fetchCurrentCar(buildList.car_id);
    } else {
      setSelectedMake('');
      setSelectedModel('');
      setSelectedGeneration(null);
    }
  }, [buildList.car_id, fetchCurrentCar]);

  useEffect(() => {
    if (currentCarData) {
      const car = normalizeCarRead(currentCarData);
      if (car) {
        setSelectedMake(car.car_make_name);
        setSelectedModel(car.car_model_name);
        setSelectedGeneration(car);
      }
    }
  }, [currentCarData]);

  useEffect(() => {
    setName(buildList.name);
    setDescription(buildList.description || '');
    setBasePriceDollars(
      buildList.base_price_cents
        ? (buildList.base_price_cents / 100).toFixed(2)
        : ''
    );
    setImageFileKey(null);
    setImageChanged(false);
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

    const payload: BuildListUpdate = {
      name: name.trim(),
      description: description.trim() || null,
      car_id: selectedGeneration?.id || null,
      base_price_cents: basePriceCents,
    };

    const result = await executeUpdateBuildList({
      buildListId: buildList.id,
      data: payload,
    });

    if (result) {
      let updated = result;
      if (imageChanged) {
        try {
          if (imageFileKey) {
            const appended = await buildListsApi.appendBuildListImages(
              buildList.id,
              [imageFileKey]
            );
            updated = appended.data;
          } else {
            const removed = await buildListsApi.removeBuildListImage(
              buildList.id,
              0
            );
            updated = removed.data;
          }
        } catch (err) {
          setFormMessage({
            type: 'error',
            text:
              err instanceof Error ? err.message : 'Failed to update image.',
          });
          return;
        }
      }
      setFormMessage({
        type: 'success',
        text: 'Build list updated successfully!',
      });
      onBuildListUpdated(updated);
    }
  };

  const uniqueModels = Array.from(
    new Set(
      availableCars.map((car) => car.car_model_name ?? '').filter(Boolean)
    )
  ).sort();

  const generations = availableCars
    .filter(
      (car) =>
        (car.car_make_name ?? '') === selectedMake &&
        (car.car_model_name ?? '') === selectedModel
    )
    .sort((a, b) => {
      if (a.start_year !== b.start_year) {
        return a.start_year - b.start_year;
      }
      return a.generation_name.localeCompare(b.generation_name);
    });

  return (
    <div className="p-4">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-200">
            Select Car (Optional)
          </h3>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              {selectedMake ? (
                <button
                  type="button"
                  onClick={() => {
                    if (selectedModel) {
                      setSelectedModel('');
                      setSelectedGeneration(null);
                    } else {
                      setSelectedMake('');
                      setSelectedModel('');
                      setSelectedGeneration(null);
                    }
                  }}
                  className="text-info hover:text-info/90 transition-colors"
                >
                  {selectedModel
                    ? '← Back to Car Models'
                    : '← Back to Manufacturers'}
                </button>
              ) : (
                'Manufacturer'
              )}
            </label>
            {!selectedMake && (
              <>
                {isLoadingMakes ? (
                  <Card>
                    <div className="flex items-center justify-center py-4">
                      <Spinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {availableMakes.map((make) => (
                      <Card
                        key={make}
                        onClick={() => setSelectedMake(make)}
                        className="text-center p-5 min-h-[100px] flex items-center justify-center cursor-pointer hover:border-info hover:scale-105 border-2 border-transparent transition-colors"
                      >
                        <h4 className="text-base font-semibold text-gray-200 break-words px-3 w-full">
                          {make}
                        </h4>
                      </Card>
                    ))}
                  </div>
                )}
              </>
            )}

            {selectedMake && !selectedModel && (
              <>
                <label className="block text-sm font-medium text-gray-300 mb-2 mt-4">
                  Model
                </label>
                {isLoadingCars ? (
                  <Card>
                    <div className="flex items-center justify-center py-4">
                      <Spinner />
                    </div>
                  </Card>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {uniqueModels.map((model) => (
                      <Card
                        key={model}
                        onClick={() => setSelectedModel(model)}
                        className="text-center p-5 min-h-[100px] flex items-center justify-center cursor-pointer hover:border-info hover:scale-105 border-2 border-transparent transition-colors"
                      >
                        <h4 className="text-base font-semibold text-gray-200 break-words px-3 w-full">
                          {model}
                        </h4>
                      </Card>
                    ))}
                  </div>
                )}
              </>
            )}

            {selectedMake && selectedModel && !selectedGeneration && (
              <>
                <label className="block text-sm font-medium text-gray-300 mb-2 mt-4">
                  Generation
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  {generations.map((car) => (
                    <Card
                      key={car.id}
                      onClick={() => setSelectedGeneration(car)}
                      className="cursor-pointer hover:border-info hover:scale-105 border-2 border-transparent transition-colors p-5"
                    >
                      <h4 className="text-base font-semibold text-info mb-1 break-words px-1">
                        {carGenerationDisplayName(car)}
                      </h4>
                      <p className="text-xs text-gray-400">
                        {formatCarYearRange(car.start_year, car.end_year)}
                      </p>
                    </Card>
                  ))}
                </div>
              </>
            )}

            {selectedGeneration && (
              <Card className="mt-4 bg-gray-800">
                <div className="flex items-center justify-between p-3">
                  <div>
                    <h4 className="text-base font-semibold text-gray-200">
                      Selected: {carFullDisplayName(selectedGeneration)}
                    </h4>
                    <p className="text-sm text-gray-400">
                      {formatCarYearRange(
                        selectedGeneration.start_year,
                        selectedGeneration.end_year
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedMake('');
                      setSelectedModel('');
                      setSelectedGeneration(null);
                    }}
                    className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors text-sm"
                  >
                    Change
                  </button>
                </div>
              </Card>
            )}

            {selectedGeneration && (
              <button
                type="button"
                onClick={() => {
                  setSelectedMake('');
                  setSelectedModel('');
                  setSelectedGeneration(null);
                }}
                className="mt-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors text-sm"
              >
                Remove Car Assignment
              </button>
            )}
          </div>
        </div>

        <div>
          <label
            htmlFor="edit-buildlist-name"
            className="block text-sm font-medium text-foreground mb-2"
          >
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
          <label
            htmlFor="edit-buildlist-description"
            className="block text-sm font-medium text-foreground mb-2"
          >
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
          <label
            htmlFor="edit-buildlist-base-price"
            className="block text-sm font-medium text-foreground mb-2"
          >
            Base Car Price (Optional)
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
              $
            </span>
            <Input
              id="edit-buildlist-base-price"
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
            Purchase price of the donor car. Included in the build's total cost.
          </p>
        </div>
        <ImageUpload
          currentImageUrl={buildList.image_urls?.[0] ?? null}
          entityType="build_list"
          entityId={buildList.id}
          onImageUploaded={(fileKey) => {
            setImageFileKey(fileKey);
            setImageChanged(true);
          }}
          onImageRemoved={() => {
            setImageFileKey(null);
            setImageChanged(true);
          }}
          label="Build List Image (Optional)"
          maxSizeMB={10}
        />
        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        <div className="flex space-x-2 pt-2">
          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? 'Saving...' : 'Save Changes'}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            disabled={isLoading}
            className="w-full"
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
};

export default EditBuildListForm;
