import React from 'react';
import Dialog from './Dialog';
import { ErrorAlert } from './Alerts';

interface DeleteConfirmationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  itemName: string;
  itemType?: string; // Optional: to specify "car", "build list", etc.
  isProcessing: boolean;
  error: string | null;
}

const DeleteConfirmationDialog: React.FC<DeleteConfirmationDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  itemName,
  itemType = 'item',
  isProcessing,
  error,
}) => {
  if (!isOpen) {
    return null;
  }

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title={`Confirm Deletion`}>
      <div className="text-gray-300">
        <p className="mb-4">
          Are you sure you want to delete the {itemType} "{itemName}"? This
          action cannot be undone.
        </p>
        {error && (
          <ErrorAlert message={`Failed to delete ${itemType}: ${error}`} />
        )}
        <div className="flex justify-end space-x-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-600 rounded-md text-gray-300 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
            disabled={isProcessing}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50"
            disabled={isProcessing}
          >
            {isProcessing ? 'Deleting...' : 'Confirm Delete'}
          </button>
        </div>
      </div>
    </Dialog>
  );
};

export default DeleteConfirmationDialog;
