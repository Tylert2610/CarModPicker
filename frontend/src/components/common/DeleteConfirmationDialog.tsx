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
      <div className="text-neutral-300">
        <p className="mb-6 text-lg leading-relaxed">
          Are you sure you want to delete the {itemType} <span className="font-semibold text-white">"{itemName}"</span>? This
          action cannot be undone.
        </p>
        {error && (
          <ErrorAlert message={`Failed to delete ${itemType}: ${error}`} />
        )}
        <div className="flex justify-end space-x-3 mt-8">
          <button
            type="button"
            onClick={onClose}
            className="glass-button px-6 py-3 rounded-xl text-neutral-300 hover:text-white transition-all duration-300"
            disabled={isProcessing}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-6 py-3 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white rounded-xl font-semibold transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
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
