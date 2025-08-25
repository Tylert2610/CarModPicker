import React, { useState } from 'react';
import { globalPartReportsApi } from '../../services/Api';
import Dialog from '../common/Dialog';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';

interface ReportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  partId: number;
  partName: string;
  onReportSubmitted?: () => void;
}

const REPORT_REASONS = [
  'Inappropriate content',
  'Spam or misleading information',
  'Incorrect specifications',
  'Duplicate part',
  'Other',
];

const ReportDialog: React.FC<ReportDialogProps> = ({
  isOpen,
  onClose,
  partId,
  partName,
  onReportSubmitted,
}) => {
  const [reason, setReason] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!reason.trim()) return;

    try {
      setIsSubmitting(true);
      await globalPartReportsApi.reportGlobalPart(partId, {
        reason: reason.trim(),
        description: description.trim() || undefined,
      });

      // Reset form
      setReason('');
      setDescription('');

      // Close dialog and notify parent
      onClose();
      onReportSubmitted?.();
    } catch (error) {
      console.error('Failed to submit report:', error);
      // You might want to show an error message here
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setReason('');
      setDescription('');
      onClose();
    }
  };

  return (
    <Dialog isOpen={isOpen} onClose={handleClose} title="Report Part">
      <div className="space-y-4">
        <div>
          <p className="text-gray-300 mb-2">
            Report: <span className="font-semibold text-white">{partName}</span>
          </p>
          <p className="text-sm text-gray-400">
            Help us maintain quality by reporting inappropriate or incorrect
            content.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Reason for Report *
          </label>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isSubmitting}
          >
            <option value="">Select a reason</option>
            {REPORT_REASONS.map((reportReason) => (
              <option key={reportReason} value={reportReason}>
                {reportReason}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Additional Details (Optional)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Please provide any additional details about your report..."
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            rows={4}
            disabled={isSubmitting}
          />
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <SecondaryButton onClick={handleClose} disabled={isSubmitting}>
            Cancel
          </SecondaryButton>
          <ActionButton
            onClick={() => void handleSubmit()}
            disabled={!reason.trim() || isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : 'Submit Report'}
          </ActionButton>
        </div>
      </div>
    </Dialog>
  );
};

export default ReportDialog;
