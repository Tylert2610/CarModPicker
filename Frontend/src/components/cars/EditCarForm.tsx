import React, { useState, useEffect } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { CarUpdate, CarRead } from '../../types/Api';
import Input from '../common/Input';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert, ConfirmationAlert } from '../common/Alerts';
import SecondaryButton from '../buttons/SecondaryButton';

interface EditCarFormProps {
  car: CarRead;
  onCarUpdated: (updatedCar: CarRead) => void;
  onCancel: () => void;
}

const updateCarRequestFn = (payload: { carId: number; data: CarUpdate }) =>
  apiClient.put<CarRead>(`/cars/${payload.carId}`, payload.data);

const EditCarForm: React.FC<EditCarFormProps> = ({
  car,
  onCarUpdated,
  onCancel,
}) => {
  const [make, setMake] = useState(car.make);
  const [model, setModel] = useState(car.model);
  const [year, setYear] = useState<number | ''>(car.year);
  const [trim, setTrim] = useState(car.trim || '');
  const [vin, setVin] = useState(car.vin || '');
  const [imageUrl, setImageUrl] = useState(car.image_url || '');
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeUpdateCar,
    setError: setApiError,
  } = useApiRequest(updateCarRequestFn);

  useEffect(() => {
    setMake(car.make);
    setModel(car.model);
    setYear(car.year);
    setTrim(car.trim || '');
    setVin(car.vin || '');
    setImageUrl(car.image_url || '');
    setApiError(null);
    setFormMessage(null);
  }, [car, setApiError]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);
    setFormMessage(null);

    if (!make.trim() || !model.trim() || year === '') {
      setFormMessage({
        type: 'error',
        text: 'Make, Model, and Year are required.',
      });
      return;
    }
    if (
      isNaN(Number(year)) ||
      Number(year) < 1886 ||
      Number(year) > new Date().getFullYear() + 1
    ) {
      setFormMessage({ type: 'error', text: 'Please enter a valid year.' });
      return;
    }

    const payload: CarUpdate = {
      make: make.trim(),
      model: model.trim(),
      year: Number(year),
      trim: trim.trim() || null,
      vin: vin.trim() || null,
      image_url: imageUrl.trim() || null,
    };

    // Check if any data actually changed
    let hasChanges = false;
    if (payload.make !== car.make) hasChanges = true;
    if (payload.model !== car.model) hasChanges = true;
    if (payload.year !== car.year) hasChanges = true;
    if (payload.trim !== (car.trim || null)) hasChanges = true;
    if (payload.vin !== (car.vin || null)) hasChanges = true;
    if (payload.image_url !== (car.image_url || null)) hasChanges = true;

    if (!hasChanges) {
      setFormMessage({ type: 'error', text: 'No changes detected.' });
      return;
    }

    const result = await executeUpdateCar({ carId: car.id, data: payload });

    if (result) {
      setFormMessage({ type: 'success', text: 'Car updated successfully!' });
      onCarUpdated(result);
    }
  };

  return (
    <div className="p-1">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Make"
          id="edit-make"
          name="make"
          type="text"
          value={make}
          onChange={(e) => setMake(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Model"
          id="edit-model"
          name="model"
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Year"
          id="edit-year"
          name="year"
          type="number"
          value={year}
          onChange={(e) =>
            setYear(e.target.value === '' ? '' : parseInt(e.target.value, 10))
          }
          required
          disabled={isLoading}
        />
        <Input
          label="Trim (Optional)"
          id="edit-trim"
          name="trim"
          type="text"
          value={trim}
          onChange={(e) => setTrim(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="VIN (Optional)"
          id="edit-vin"
          name="vin"
          type="text"
          value={vin}
          onChange={(e) => setVin(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Image URL (Optional)"
          id="edit-image_url"
          name="image_url"
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          disabled={isLoading}
          placeholder="https://example.com/car-image.png"
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

export default EditCarForm;