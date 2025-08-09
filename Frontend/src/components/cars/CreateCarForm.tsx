import React, { useState } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { CarCreate, CarRead } from '../../types/Api';
import Input from '../common/Input';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert, ConfirmationAlert } from '../common/Alerts';
import SectionHeader from '../layout/SectionHeader';
import Card from '../common/Card';

interface CreateCarFormProps {
  onCarCreated: (newCar: CarRead) => void;
}

const createCarRequestFn = (payload: CarCreate) =>
  apiClient.post<CarRead>('/cars/', payload);

const CreateCarForm: React.FC<CreateCarFormProps> = ({ onCarCreated }) => {
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [year, setYear] = useState<number | ''>('');
  const [trim, setTrim] = useState('');
  const [vin, setVin] = useState('');
  const [imageUrl, setImageUrl] = useState(''); 
  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeCreateCar,
    setError: setApiError,
  } = useApiRequest(createCarRequestFn);

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

    const payload: CarCreate = {
      make: make.trim(),
      model: model.trim(),
      year: Number(year),
      trim: trim.trim() || null,
      vin: vin.trim() || null,
      image_url: imageUrl.trim() || null, 
    };

    const result = await executeCreateCar(payload);

    if (result) {
      setFormMessage({ type: 'success', text: 'Car created successfully!' });
      onCarCreated(result);
     
      setMake('');
      setModel('');
      setYear('');
      setTrim('');
      setVin('');
      setImageUrl(''); 
    } else {
      // apiError will be set by the hook
      // setFormMessage({ type: 'error', text: apiError || 'Failed to create car.' });
    }
  };

  return (
    <Card className="mb-6">
      <SectionHeader title="Add a New Car" />
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Make"
          id="make"
          name="make"
          type="text"
          value={make}
          onChange={(e) => setMake(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Model"
          id="model"
          name="model"
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input
          label="Year"
          id="year"
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
          id="trim"
          name="trim"
          type="text"
          value={trim}
          onChange={(e) => setTrim(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="VIN (Optional)"
          id="vin"
          name="vin"
          type="text"
          value={vin}
          onChange={(e) => setVin(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Image URL (Optional)"
          id="image_url"
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
        <ButtonStretch type="submit" disabled={isLoading}>
          {isLoading ? 'Adding Car...' : 'Add Car'}
        </ButtonStretch>
      </form>
    </Card>
  );
};

export default CreateCarForm;
