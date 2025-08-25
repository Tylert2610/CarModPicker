import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  GlobalPartReportWithDetails,
  GlobalPartReportUpdate,
} from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Dialog from '../../components/common/Dialog';

const fetchReportsRequestFn = (params?: {
  status?: string;
  skip?: number;
  limit?: number;
}) =>
  apiClient.get<GlobalPartReportWithDetails[]>('/global-part-reports/reports', {
    params,
  });
const updateReportRequestFn = (payload: {
  reportId: number;
  data: GlobalPartReportUpdate;
}) =>
  apiClient.put<GlobalPartReportWithDetails>(
    `/global-part-reports/reports/${payload.reportId}`,
    payload.data
  );
const getPendingReportsCountRequestFn = () =>
  apiClient.get<Record<string, number>>(
    '/global-part-reports/reports/pending/count'
  );

function ReportReview() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [selectedStatus, setSelectedStatus] = useState<string>('pending');
  const [isReviewDialogOpen, setIsReviewDialogOpen] = useState(false);
  const [selectedReport, setSelectedReport] =
    useState<GlobalPartReportWithDetails | null>(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [pendingCount, setPendingCount] = useState<number>(0);

  const {
    data: reports,
    isLoading: isLoadingReports,
    error: reportsError,
    executeRequest: fetchReports,
  } = useApiRequest(fetchReportsRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateReportRequestFn);

  const { data: countData, executeRequest: fetchPendingCount } = useApiRequest(
    getPendingReportsCountRequestFn
  );

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  useEffect(() => {
    void fetchReports({ status: selectedStatus });
    void fetchPendingCount();
  }, [fetchReports, fetchPendingCount, selectedStatus]);

  useEffect(() => {
    if (countData) {
      setPendingCount(countData.pending_count || 0);
    }
  }, [countData]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Report Review" />
        <Card>
          <ErrorAlert message="Please log in to access report review." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Report Review" />
        <Card>
          <ErrorAlert message="You do not have permission to access report review." />
        </Card>
      </div>
    );
  }

  const handleUpdateReport = async (status: 'resolved' | 'dismissed') => {
    if (!selectedReport) return;

    const result = await executeUpdate({
      reportId: selectedReport.id,
      data: {
        status,
        admin_notes: adminNotes,
      },
    });

    if (result) {
      setIsReviewDialogOpen(false);
      setSelectedReport(null);
      setAdminNotes('');
      void fetchReports({ status: selectedStatus });
      void fetchPendingCount();
    }
  };

  const openReviewDialog = (report: GlobalPartReportWithDetails) => {
    setUpdateError(null);
    setSelectedReport(report);
    setAdminNotes(report.admin_notes || '');
    setIsReviewDialogOpen(true);
  };

  const closeReviewDialog = () => {
    setIsReviewDialogOpen(false);
    setSelectedReport(null);
    setAdminNotes('');
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      pending: { color: 'bg-yellow-600 text-yellow-100', text: 'Pending' },
      resolved: { color: 'bg-green-600 text-green-100', text: 'Resolved' },
      dismissed: { color: 'bg-gray-600 text-gray-100', text: 'Dismissed' },
    };

    const config =
      statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
    return (
      <span className={`px-2 py-1 rounded text-xs ${config.color}`}>
        {config.text}
      </span>
    );
  };

  if (isLoadingReports && !reports) {
    return (
      <>
        <PageHeader title="Report Review" />
        <LoadingSpinner />
      </>
    );
  }

  return (
    <div>
      <PageHeader
        title="Report Review"
        subtitle="Review and manage part reports"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
        <div className="flex space-x-2">
          <ActionButton
            onClick={() => setSelectedStatus('pending')}
            className={
              selectedStatus === 'pending' ? 'bg-blue-600' : 'bg-gray-600'
            }
          >
            Pending ({pendingCount})
          </ActionButton>
          <ActionButton
            onClick={() => setSelectedStatus('resolved')}
            className={
              selectedStatus === 'resolved' ? 'bg-blue-600' : 'bg-gray-600'
            }
          >
            Resolved
          </ActionButton>
          <ActionButton
            onClick={() => setSelectedStatus('dismissed')}
            className={
              selectedStatus === 'dismissed' ? 'bg-blue-600' : 'bg-gray-600'
            }
          >
            Dismissed
          </ActionButton>
        </div>
      </div>

      {reportsError && (
        <Card>
          <ErrorAlert message={`Failed to load reports: ${reportsError}`} />
        </Card>
      )}

      {reports && (
        <Card>
          <SectionHeader
            title={`${selectedStatus.charAt(0).toUpperCase() + selectedStatus.slice(1)} Reports`}
          />
          {reports.length === 0 ? (
            <p className="text-gray-400 text-center py-8">
              No {selectedStatus} reports found.
            </p>
          ) : (
            <div className="space-y-4">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="border border-gray-700 rounded-lg p-4"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-200">
                        Report #{report.id} - {report.part_name}
                      </h3>
                      <p className="text-gray-400">
                        Reported by {report.reporter_username} on{' '}
                        {new Date(report.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      {getStatusBadge(report.status)}
                      {report.status === 'pending' && (
                        <ActionButton
                          onClick={() => openReviewDialog(report)}
                          className="text-sm px-3 py-1"
                        >
                          Review
                        </ActionButton>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                    <div>
                      <h4 className="font-medium text-gray-300 mb-1">Reason</h4>
                      <p className="text-gray-400">{report.reason}</p>
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-300 mb-1">
                        Part Details
                      </h4>
                      <p className="text-gray-400">
                        {report.part_name}
                        {report.part_brand && ` - ${report.part_brand}`}
                      </p>
                    </div>
                  </div>

                  {report.description && (
                    <div className="mb-3">
                      <h4 className="font-medium text-gray-300 mb-1">
                        Description
                      </h4>
                      <p className="text-gray-400">{report.description}</p>
                    </div>
                  )}

                  {report.admin_notes && (
                    <div className="mb-3">
                      <h4 className="font-medium text-gray-300 mb-1">
                        Admin Notes
                      </h4>
                      <p className="text-gray-400">{report.admin_notes}</p>
                    </div>
                  )}

                  {report.reviewer_username && (
                    <div className="text-sm text-gray-500">
                      Reviewed by {report.reviewer_username} on{' '}
                      {report.reviewed_at &&
                        new Date(report.reviewed_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Review Dialog */}
      <Dialog
        isOpen={isReviewDialogOpen}
        onClose={closeReviewDialog}
        title={`Review Report #${selectedReport?.id}`}
      >
        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-300 mb-2">Report Details</h4>
            <div className="bg-gray-800 p-3 rounded">
              <p>
                <strong>Part:</strong> {selectedReport?.part_name}
              </p>
              <p>
                <strong>Reason:</strong> {selectedReport?.reason}
              </p>
              <p>
                <strong>Reporter:</strong> {selectedReport?.reporter_username}
              </p>
              {selectedReport?.description && (
                <p>
                  <strong>Description:</strong> {selectedReport.description}
                </p>
              )}
            </div>
          </div>

          <div>
            <label
              htmlFor="admin_notes"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Admin Notes
            </label>
            <textarea
              id="admin_notes"
              value={adminNotes}
              onChange={(e) => setAdminNotes(e.target.value)}
              className="w-full p-2 bg-gray-800 border border-gray-600 rounded text-gray-200"
              rows={4}
              placeholder="Add notes about your decision..."
            />
          </div>

          {updateError && <ErrorAlert message={updateError} />}

          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeReviewDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateReport('dismissed')}
              className="bg-gray-600 hover:bg-gray-700"
              disabled={isUpdating}
            >
              Dismiss Report
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateReport('resolved')}
              className="bg-green-600 hover:bg-green-700"
              disabled={isUpdating}
            >
              Resolve Report
            </ActionButton>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

export default ReportReview;
