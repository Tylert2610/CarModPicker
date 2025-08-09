import React, { useState } from 'react';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { PartCreate, PartRead } from '../../types/Api';
import Input from '../common/Input';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert, ConfirmationAlert } from '../common/Alerts';

interface CreatePartFormProps {
  buildListId: number;
  onPartCreated: (newPart: PartRead) => void;
}

const createPartRequestFn = (payload: PartCreate) =>
  apiClient.post<PartRead>('/parts/', payload);

const CreatePartForm: React.FC<CreatePartFormProps> = ({
  buildListId,
  onPartCreated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [partNumber, setPartNumber] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [purchaseUrl, setPurchaseUrl] = useState('');
  const [price, setPrice] = useState<number | ''>('');
  const [notes, setNotes] = useState('');

  const [formMessage, setFormMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const {
    error: apiError,
    isLoading,
    executeRequest: executeCreatePart,
    setError: setApiError,
  } = useApiRequest(createPartRequestFn);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);
    setFormMessage(null);

    if (!name.trim()) {
      setFormMessage({
        type: 'error',
        text: 'Part name is required.',
      });
      return;
    }

    const payload: PartCreate = {
      name: name.trim(),
      description: description.trim() || null,
      image_url: imageUrl.trim() || null,
      part_number: partNumber.trim() || null,
      manufacturer: manufacturer.trim() || null,
      price: price === '' ? null : Number(price),
      build_list_id: buildListId,
    };

    const result = await executeCreatePart(payload);

    if (result) {
      setFormMessage({
        type: 'success',
        text: 'Part created successfully!',
      });
      onPartCreated(result);
      // Reset form
      setName('');
      setDescription('');
      setImageUrl('');
      setPartNumber('');
      setManufacturer('');
      setPurchaseUrl('');
      setPrice('');
      setNotes('');
    }
  };

  return (
    <div className="p-1">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Part Name"
          id="part-name"
          name="part-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          disabled={isLoading}
        />
        <Input 
          label="Description (Optional)"
          id="part-description"
          name="part-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Image URL (Optional)"
          id="part-image_url"
          name="part-image_url"
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          disabled={isLoading}
          placeholder="https://example.com/part-image.png"
        />
        <Input
          label="Part Number (Optional)"
          id="part-part_number"
          name="part_number"
          type="text"
          value={partNumber}
          onChange={(e) => setPartNumber(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Manufacturer (Optional)"
          id="part-manufacturer"
          name="manufacturer"
          type="text"
          value={manufacturer}
          onChange={(e) => setManufacturer(e.target.value)}
          disabled={isLoading}
        />
        <Input
          label="Purchase URL (Optional)"
          id="part-purchase_url"
          name="purchase_url"
          type="url"
          value={purchaseUrl}
          onChange={(e) => setPurchaseUrl(e.target.value)}
          disabled={isLoading}
          placeholder="https://example.com/store/part"
        />
        <Input
          label="Price (Optional)"
          id="part-price"
          name="price"
          type="number"
          value={price}
          onChange={(e) =>
            setPrice(e.target.value === '' ? '' : parseFloat(e.target.value))
          }
          disabled={isLoading}
          step="0.01"
          placeholder="e.g., 19.99"
          
        />
        <Input
          label="Notes (Optional)"
          id="part-notes"
          name="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isLoading}
        />
        {formMessage?.type === 'success' && (
          <ConfirmationAlert message={formMessage.text} />
        )}
        {(apiError || formMessage?.type === 'error') && (
          <ErrorAlert message={apiError || formMessage?.text || null} />
        )}
        <ButtonStretch type="submit" disabled={isLoading}>
          {isLoading ? 'Adding Part...' : 'Add Part'}
        </ButtonStretch>
      </form>
    </div>
  );
};

export default CreatePartForm;
