import React, { useState } from 'react';
import type {
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
} from '../../types/Api';
import Dialog from '../common/Dialog';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';

interface EditBuildListPartFormProps {
  buildListPart: BuildListPartReadWithGlobalPart;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (
    buildListPartId: number,
    data: BuildListPartUpdate
  ) => Promise<void>;
  loading?: boolean;
}

const EditBuildListPartForm: React.FC<EditBuildListPartFormProps> = ({
  buildListPart,
  isOpen,
  onClose,
  onSubmit,
  loading = false,
}) => {
  const [notes, setNotes] = useState(buildListPart.notes || '');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    void onSubmit(buildListPart.id, { notes: notes || null })
      .then(() => onClose())
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to update notes');
      });
  };

  const handleClose = () => {
    setNotes(buildListPart.notes || '');
    setError(null);
    onClose();
  };

  return (
    <Dialog isOpen={isOpen} onClose={handleClose} title="Edit Part Notes">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">
            {buildListPart.global_part.name}
          </h3>
          <p className="text-gray-400 text-sm mb-4">
            Add your personal notes about this part in your build list.
          </p>
        </div>

        <div>
          <label
            htmlFor="notes"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Notes
          </label>
          <textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add your notes about this part..."
            rows={4}
            className="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-white"
          />
        </div>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded p-2">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-4">
          <SecondaryButton
            type="button"
            onClick={handleClose}
            disabled={loading}
          >
            Cancel
          </SecondaryButton>
          <ActionButton type="submit" disabled={loading}>
            {loading ? 'Saving...' : 'Save Notes'}
          </ActionButton>
        </div>
      </form>
    </Dialog>
  );
};

export default EditBuildListPartForm;
