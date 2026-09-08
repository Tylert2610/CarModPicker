import React, { useState } from 'react';
import { partReportsApi } from '../../api/reports';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';

interface ReportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  partId: string;
  partName: string;
  onReportSubmitted?: () => void;
}

const REPORT_REASONS = [
  { display: 'Inappropriate content', value: 'inappropriate' },
  { display: 'Spam or misleading information', value: 'spam' },
  { display: 'Incorrect details', value: 'inaccurate' },
  { display: 'Duplicate part', value: 'duplicate' },
  { display: 'Other', value: 'other' },
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
      await partReportsApi.reportPart(partId, {
        reason: reason.trim(),
        description: description.trim() || null,
      });

      // Reset form
      setReason('');
      setDescription('');

      // Close dialog and notify parent
      onClose();
      onReportSubmitted?.();
    } catch {
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
    <Dialog
      open={isOpen}
      onOpenChange={(next) => {
        if (!next) handleClose();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Report Part</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <p className="text-gray-300 mb-2">
              Report:{' '}
              <span className="font-semibold text-white">{partName}</span>
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
                <option key={reportReason.value} value={reportReason.value}>
                  {reportReason.display}
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
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void handleSubmit()}
              disabled={!reason.trim() || isSubmitting}
            >
              {isSubmitting ? 'Submitting...' : 'Submit Report'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ReportDialog;
