import type { AxiosResponse } from 'axios';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { bugReportsApi } from '../../api/bug_reports';
import { apiClient } from '../../api/client';
import type {
  BugReportUpdate,
  BugReportWithDetails,
  PaginatedResponse,
} from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { LoadingOverlay } from '../../components/ui/loading-overlay';
import Pagination from '../../components/ui/pagination';
import Spinner from '../../components/ui/spinner';
import { PriorityBadge, StatusBadge } from '../../components/ui/status-badge';
import { Textarea } from '../../components/ui/textarea';
import { ADMIN_ITEMS_PER_PAGE } from '../../constants';

const fetchBugReportsRequestFn = (params?: {
  status?: string;
  priority?: string;
  skip?: number;
  limit?: number;
}): Promise<AxiosResponse<PaginatedResponse<BugReportWithDetails>>> =>
  bugReportsApi.getBugReportsWithDetails(params);
const updateBugReportRequestFn = (payload: {
  bugReportId: string;
  data: BugReportUpdate;
}): Promise<AxiosResponse<BugReportWithDetails>> =>
  apiClient.put<BugReportWithDetails>(
    `/bug-reports/${payload.bugReportId}`,
    payload.data
  );
const getPendingBugReportsCountRequestFn = (): Promise<
  AxiosResponse<PaginatedResponse<BugReportWithDetails>>
> =>
  bugReportsApi.getBugReportsWithDetails({
    status: 'pending',
    skip: 0,
    limit: 1,
  });

function BugReportReview() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [selectedStatus, setSelectedStatus] = useState<string>('pending');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [isReviewDialogOpen, setIsReviewDialogOpen] = useState(false);
  const [selectedBugReport, setSelectedBugReport] =
    useState<BugReportWithDetails | null>(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [priority, setPriority] = useState<string>('medium');
  const [pendingCount, setPendingCount] = useState<number>(0);

  const {
    data: bugReportsData,
    isLoading: isLoadingBugReports,
    error: bugReportsError,
    executeRequest: fetchBugReports,
  } = useApiRequest<
    PaginatedResponse<BugReportWithDetails>,
    {
      status?: string;
      priority?: string;
      skip?: number;
      limit?: number;
    }
  >(fetchBugReportsRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateBugReportRequestFn);

  const { data: countData, executeRequest: fetchPendingCount } = useApiRequest<
    PaginatedResponse<BugReportWithDetails>,
    never
  >(getPendingBugReportsCountRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  // Reset to page 1 when status or priority changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedStatus, selectedPriority]);

  useEffect(() => {
    void fetchBugReports({
      ...(selectedStatus !== 'all' && { status: selectedStatus }),
      ...(selectedPriority !== 'all' && { priority: selectedPriority }),
      skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
      limit: ADMIN_ITEMS_PER_PAGE,
    });
    void fetchPendingCount();
  }, [
    fetchBugReports,
    fetchPendingCount,
    selectedStatus,
    selectedPriority,
    currentPage,
  ]);

  useEffect(() => {
    if (
      countData &&
      typeof countData === 'object' &&
      'pagination' in countData &&
      countData.pagination &&
      typeof countData.pagination === 'object' &&
      'total_items' in countData.pagination &&
      typeof countData.pagination.total_items === 'number'
    ) {
      setPendingCount(countData.pagination.total_items);
    }
  }, [countData]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Bug Report Review" />
        <Card>
          <ErrorAlert message="Please log in to access bug report review." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Bug Report Review" />
        <Card>
          <ErrorAlert message="You do not have permission to access bug report review." />
        </Card>
      </div>
    );
  }

  const handleUpdateBugReport = async (
    newStatus: 'resolved' | 'dismissed' | 'in_progress'
  ) => {
    if (!selectedBugReport) return;

    const result = await executeUpdate({
      bugReportId: selectedBugReport.id,
      data: {
        status: newStatus,
        priority: priority as 'low' | 'medium' | 'high' | 'critical',
        admin_notes: adminNotes,
      },
    });

    if (result) {
      setIsReviewDialogOpen(false);
      setSelectedBugReport(null);
      setAdminNotes('');
      void fetchBugReports({
        ...(selectedStatus !== 'all' && { status: selectedStatus }),
        ...(selectedPriority !== 'all' && { priority: selectedPriority }),
        skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
        limit: ADMIN_ITEMS_PER_PAGE,
      });
      void fetchPendingCount();
    }
  };

  const openReviewDialog = (bugReport: BugReportWithDetails) => {
    setUpdateError(null);
    setSelectedBugReport(bugReport);
    setAdminNotes(bugReport.admin_notes || '');
    setPriority(bugReport.priority);
    setIsReviewDialogOpen(true);
  };

  const closeReviewDialog = () => {
    setIsReviewDialogOpen(false);
    setSelectedBugReport(null);
    setAdminNotes('');
  };

  const renderStatusBadge = (status: string) => {
    const variant: 'pending' | 'in_progress' | 'resolved' | 'dismissed' =
      status === 'in_progress' ||
      status === 'resolved' ||
      status === 'dismissed'
        ? status
        : 'pending';
    return <StatusBadge variant={variant} />;
  };

  const renderPriorityBadge = (priority: string) => {
    const value: 'low' | 'medium' | 'high' | 'critical' =
      priority === 'low' || priority === 'high' || priority === 'critical'
        ? priority
        : 'medium';
    return <PriorityBadge priority={value} />;
  };

  // Extract bug reports and pagination info from the response
  const bugReports: BugReportWithDetails[] =
    bugReportsData &&
    typeof bugReportsData === 'object' &&
    'data' in bugReportsData
      ? Array.isArray(bugReportsData.data)
        ? bugReportsData.data
        : []
      : [];
  const pagination =
    bugReportsData &&
    typeof bugReportsData === 'object' &&
    'pagination' in bugReportsData
      ? bugReportsData.pagination
      : undefined;

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Bug Report Review"
        subtitle="Review and manage bug reports"
      />

      <div className="flex flex-col sm:flex-row sm:items-start gap-3 mb-4">
        <div className="shrink-0">
          <Button variant="secondary" onClick={() => void navigate('/admin')}>
            ← Back to Admin Dashboard
          </Button>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <Button
              variant={selectedStatus === 'pending' ? 'default' : 'secondary'}
              onClick={() => setSelectedStatus('pending')}
            >
              Pending ({pendingCount})
            </Button>
            <Button
              variant={
                selectedStatus === 'in_progress' ? 'default' : 'secondary'
              }
              onClick={() => setSelectedStatus('in_progress')}
            >
              In Progress
            </Button>
            <Button
              variant={selectedStatus === 'resolved' ? 'default' : 'secondary'}
              onClick={() => setSelectedStatus('resolved')}
            >
              Resolved
            </Button>
            <Button
              variant={selectedStatus === 'dismissed' ? 'default' : 'secondary'}
              onClick={() => setSelectedStatus('dismissed')}
            >
              Dismissed
            </Button>
            <Button
              variant={selectedStatus === 'all' ? 'default' : 'secondary'}
              onClick={() => setSelectedStatus('all')}
            >
              All
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground shrink-0">
              Priority:
            </span>
            {['all', 'low', 'medium', 'high', 'critical'].map((p) => (
              <Button
                key={p}
                variant={selectedPriority === p ? 'default' : 'secondary'}
                onClick={() => setSelectedPriority(p)}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {bugReportsError && (
        <Card>
          <ErrorAlert
            message={`Failed to load bug reports: ${bugReportsError}`}
          />
        </Card>
      )}

      {isLoadingBugReports && !bugReportsData ? (
        <Card>
          <div className="flex justify-center items-center py-16">
            <Spinner />
          </div>
        </Card>
      ) : bugReportsData ? (
        <Card className="relative">
          <LoadingOverlay visible={isLoadingBugReports} />
          <SectionHeader
            title={`${
              selectedStatus === 'all'
                ? 'All'
                : selectedStatus.charAt(0).toUpperCase() +
                  selectedStatus.slice(1)
            } Bug Reports`}
          />
          {bugReports.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No bug reports found.
            </p>
          ) : (
            <>
              <div className="space-y-4">
                {bugReports.map((bugReport) => (
                  <div
                    key={bugReport.id}
                    className="border border-border rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">
                          #{bugReport.id} - {bugReport.title}
                        </h3>
                        <p className="text-muted-foreground">
                          Reported by{' '}
                          {bugReport.reporter_username || 'Anonymous'} on{' '}
                          {new Date(bugReport.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        {renderStatusBadge(bugReport.status)}
                        {renderPriorityBadge(bugReport.priority)}
                        {(bugReport.status === 'pending' ||
                          bugReport.status === 'in_progress') && (
                          <Button
                            size="sm"
                            onClick={() => openReviewDialog(bugReport)}
                          >
                            Review
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="mb-3">
                      <h4 className="font-medium text-foreground mb-1">
                        Description
                      </h4>
                      <p className="text-muted-foreground">
                        {bugReport.description}
                      </p>
                    </div>

                    {bugReport.steps_to_reproduce && (
                      <div className="mb-3">
                        <h4 className="font-medium text-foreground mb-1">
                          Steps to Reproduce
                        </h4>
                        <p className="text-muted-foreground">
                          {bugReport.steps_to_reproduce}
                        </p>
                      </div>
                    )}

                    {bugReport.expected_behavior && (
                      <div className="mb-3">
                        <h4 className="font-medium text-foreground mb-1">
                          Expected Behavior
                        </h4>
                        <p className="text-muted-foreground">
                          {bugReport.expected_behavior}
                        </p>
                      </div>
                    )}

                    {bugReport.actual_behavior && (
                      <div className="mb-3">
                        <h4 className="font-medium text-foreground mb-1">
                          Actual Behavior
                        </h4>
                        <p className="text-muted-foreground">
                          {bugReport.actual_behavior}
                        </p>
                      </div>
                    )}

                    {(bugReport.browser_info || bugReport.device_info) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                        {bugReport.browser_info && (
                          <div>
                            <h4 className="font-medium text-foreground mb-1">
                              Browser Info
                            </h4>
                            <p className="text-muted-foreground">
                              {bugReport.browser_info}
                            </p>
                          </div>
                        )}
                        {bugReport.device_info && (
                          <div>
                            <h4 className="font-medium text-foreground mb-1">
                              Device Info
                            </h4>
                            <p className="text-muted-foreground">
                              {bugReport.device_info}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {bugReport.screenshot_url && (
                      <div className="mb-3">
                        <h4 className="font-medium text-foreground mb-1">
                          Screenshot
                        </h4>
                        <img
                          src={bugReport.screenshot_url}
                          alt="Bug screenshot"
                          className="max-w-full h-auto rounded border border-border"
                        />
                      </div>
                    )}

                    {bugReport.admin_notes && (
                      <div className="mb-3">
                        <h4 className="font-medium text-foreground mb-1">
                          Admin Notes
                        </h4>
                        <p className="text-muted-foreground">
                          {bugReport.admin_notes}
                        </p>
                      </div>
                    )}

                    {bugReport.assignee_username && (
                      <div className="text-sm text-muted-foreground">
                        Assigned to {bugReport.assignee_username}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {pagination &&
                typeof pagination === 'object' &&
                'current_page' in pagination &&
                'total_pages' in pagination &&
                'total_items' in pagination && (
                  <Pagination
                    currentPage={
                      typeof pagination.current_page === 'number'
                        ? pagination.current_page
                        : 1
                    }
                    totalPages={
                      typeof pagination.total_pages === 'number'
                        ? pagination.total_pages
                        : 1
                    }
                    onPageChange={setCurrentPage}
                    itemsPerPage={ADMIN_ITEMS_PER_PAGE}
                    totalItems={
                      typeof pagination.total_items === 'number'
                        ? pagination.total_items
                        : 0
                    }
                  />
                )}
            </>
          )}
        </Card>
      ) : null}

      {/* Review Dialog */}
      <Dialog
        open={isReviewDialogOpen}
        onOpenChange={(next) => {
          if (!next) closeReviewDialog();
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{`Review Bug Report #${selectedBugReport?.id ?? ''}`}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <h4 className="font-medium text-foreground mb-2">
                Bug Report Details
              </h4>
              <div className="bg-muted p-3 rounded text-foreground">
                <p>
                  <strong>Title:</strong> {selectedBugReport?.title}
                </p>
                <p>
                  <strong>Description:</strong> {selectedBugReport?.description}
                </p>
                <p>
                  <strong>Reporter:</strong>{' '}
                  {selectedBugReport?.reporter_username || 'Anonymous'}
                </p>
              </div>
            </div>

            <div>
              <label
                htmlFor="priority"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Priority
              </label>
              <select
                id="priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full rounded border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="admin_notes"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Admin Notes
              </label>
              <Textarea
                id="admin_notes"
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={4}
                placeholder="Add notes about your decision..."
              />
            </div>

            {updateError && <ErrorAlert message={updateError} />}

            <div className="flex justify-end space-x-2">
              <Button variant="secondary" onClick={closeReviewDialog}>
                Cancel
              </Button>
              <Button
                onClick={() => void handleUpdateBugReport('in_progress')}
                disabled={isUpdating}
              >
                Mark In Progress
              </Button>
              <Button
                variant="secondary"
                onClick={() => void handleUpdateBugReport('dismissed')}
                disabled={isUpdating}
              >
                Dismiss
              </Button>
              <Button
                onClick={() => void handleUpdateBugReport('resolved')}
                className="bg-success hover:bg-success/90 text-success-foreground"
                disabled={isUpdating}
              >
                Resolve
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default BugReportReview;
