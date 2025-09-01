import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type { SubscriptionStatus, UpgradeRequest } from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Dialog from '../../components/common/Dialog';

const fetchSubscriptionStatusRequestFn = () =>
  apiClient.get<SubscriptionStatus>('/subscriptions/subscriptions/status');
const upgradeSubscriptionRequestFn = (data: UpgradeRequest) =>
  apiClient.post<SubscriptionStatus>(
    '/subscriptions/subscriptions/upgrade',
    data
  );
const cancelSubscriptionRequestFn = () =>
  apiClient.post<SubscriptionStatus>('/subscriptions/subscriptions/cancel');

function SubscriptionManagement() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [isUpgradeDialogOpen, setIsUpgradeDialogOpen] = useState(false);
  const [isCancelDialogOpen, setIsCancelDialogOpen] = useState(false);
  const [upgradeError, setUpgradeError] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const {
    data: subscriptionStatus,
    isLoading: isLoadingStatus,
    error: statusError,
    executeRequest: fetchStatus,
  } = useApiRequest(fetchSubscriptionStatusRequestFn);

  const {
    isLoading: isUpgrading,
    error: upgradeApiError,
    executeRequest: executeUpgrade,
  } = useApiRequest(upgradeSubscriptionRequestFn);

  const {
    isLoading: isCancelling,
    error: cancelApiError,
    executeRequest: executeCancel,
  } = useApiRequest(cancelSubscriptionRequestFn);

  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (upgradeApiError) {
      setUpgradeError(upgradeApiError);
    }
  }, [upgradeApiError]);

  useEffect(() => {
    if (cancelApiError) {
      setCancelError(cancelApiError);
    }
  }, [cancelApiError]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Subscription Management" />
        <Card>
          <ErrorAlert message="Please log in to access subscription management." />
        </Card>
      </div>
    );
  }

  const handleUpgrade = async () => {
    setUpgradeError(null);
    const result = await executeUpgrade({ tier: 'premium' });
    if (result) {
      setIsUpgradeDialogOpen(false);
      void fetchStatus();
    }
  };

  const handleCancel = async () => {
    setCancelError(null);
    const result = await executeCancel();
    if (result) {
      setIsCancelDialogOpen(false);
      void fetchStatus();
    }
  };

  const openUpgradeDialog = () => {
    setUpgradeError(null);
    setIsUpgradeDialogOpen(true);
  };

  const openCancelDialog = () => {
    setCancelError(null);
    setIsCancelDialogOpen(true);
  };

  const closeUpgradeDialog = () => {
    setIsUpgradeDialogOpen(false);
    setUpgradeError(null);
  };

  const closeCancelDialog = () => {
    setIsCancelDialogOpen(false);
    setCancelError(null);
  };

  const getTierBadge = (tier: string) => {
    const tierConfig = {
      free: { color: 'bg-gray-600 text-gray-100', text: 'Free' },
      premium: { color: 'bg-yellow-600 text-yellow-100', text: 'Premium' },
    };

    const config =
      tierConfig[tier as keyof typeof tierConfig] || tierConfig.free;
    return (
      <span
        className={`px-3 py-1 rounded-full text-sm font-medium ${config.color}`}
      >
        {config.text}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      active: { color: 'bg-green-600 text-green-100', text: 'Active' },
      cancelled: { color: 'bg-red-600 text-red-100', text: 'Cancelled' },
      expired: { color: 'bg-orange-600 text-orange-100', text: 'Expired' },
    };

    const config =
      statusConfig[status as keyof typeof statusConfig] || statusConfig.active;
    return (
      <span
        className={`px-3 py-1 rounded-full text-sm font-medium ${config.color}`}
      >
        {config.text}
      </span>
    );
  };

  if (isLoadingStatus && !subscriptionStatus) {
    return (
      <>
        <PageHeader title="Subscription Management" />
        <LoadingSpinner />
      </>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Subscription Management"
        subtitle="Manage your CarModPicker subscription"
      />

      <div className="mb-4">
        <ActionButton onClick={() => void navigate('/profile')}>
          ← Back to Profile
        </ActionButton>
      </div>

      {statusError && (
        <Card>
          <ErrorAlert
            message={`Failed to load subscription status: ${statusError}`}
          />
        </Card>
      )}

      {subscriptionStatus && (
        <div className="space-y-6">
          {/* Current Subscription Status */}
          <Card>
            <SectionHeader title="Current Subscription" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-200 mb-4">
                  Plan Details
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Current Tier:</span>
                    {getTierBadge(subscriptionStatus.tier)}
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Status:</span>
                    {getStatusBadge(subscriptionStatus.status)}
                  </div>
                  {subscriptionStatus.expires_at && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Expires:</span>
                      <span className="text-gray-200">
                        {new Date(
                          subscriptionStatus.expires_at
                        ).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-200 mb-4">
                  Usage Limits
                </h3>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-gray-400">Cars</span>
                      <span className="text-gray-200">
                        {subscriptionStatus.usage.cars || 0} /{' '}
                        {subscriptionStatus.limits.cars || '∞'}
                      </span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{
                          width: `${Math.min(
                            ((subscriptionStatus.usage.cars || 0) /
                              (subscriptionStatus.limits.cars || 1)) *
                              100,
                            100
                          )}%`,
                        }}
                      ></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-gray-400">Build Lists</span>
                      <span className="text-gray-200">
                        {subscriptionStatus.usage.build_lists || 0} /{' '}
                        {subscriptionStatus.limits.build_lists || '∞'}
                      </span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-green-600 h-2 rounded-full"
                        style={{
                          width: `${Math.min(
                            ((subscriptionStatus.usage.build_lists || 0) /
                              (subscriptionStatus.limits.build_lists || 1)) *
                              100,
                            100
                          )}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Subscription Actions */}
          <Card>
            <SectionHeader title="Subscription Actions" />
            <div className="flex flex-col sm:flex-row gap-4">
              {subscriptionStatus.tier === 'free' && (
                <ActionButton
                  onClick={openUpgradeDialog}
                  className="bg-yellow-600 hover:bg-yellow-700"
                >
                  Upgrade to Premium
                </ActionButton>
              )}

              {subscriptionStatus.tier === 'premium' &&
                subscriptionStatus.status === 'active' && (
                  <ActionButton
                    onClick={openCancelDialog}
                    className="bg-red-600 hover:bg-red-700"
                  >
                    Cancel Subscription
                  </ActionButton>
                )}

              {subscriptionStatus.status === 'cancelled' && (
                <div className="text-gray-400">
                  Your subscription has been cancelled and will expire at the
                  end of the current billing period.
                </div>
              )}
            </div>
          </Card>

          {/* Premium Features */}
          {subscriptionStatus.tier === 'premium' && (
            <Card>
              <SectionHeader title="Premium Features" />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-gray-800 rounded-lg">
                  <h4 className="font-semibold text-gray-200 mb-2">
                    🚗 Unlimited Cars
                  </h4>
                  <p className="text-gray-400">
                    Create as many cars as you want
                  </p>
                </div>
                <div className="p-4 bg-gray-800 rounded-lg">
                  <h4 className="font-semibold text-gray-200 mb-2">
                    📋 Unlimited Build Lists
                  </h4>
                  <p className="text-gray-400">
                    Create unlimited build lists for your projects
                  </p>
                </div>
                <div className="p-4 bg-gray-800 rounded-lg">
                  <h4 className="font-semibold text-gray-200 mb-2">
                    ⭐ Priority Support
                  </h4>
                  <p className="text-gray-400">
                    Get faster support when you need help
                  </p>
                </div>
                <div className="p-4 bg-gray-800 rounded-lg">
                  <h4 className="font-semibold text-gray-200 mb-2">
                    🔒 Advanced Features
                  </h4>
                  <p className="text-gray-400">
                    Access to upcoming premium features
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Upgrade Dialog */}
      <Dialog
        isOpen={isUpgradeDialogOpen}
        onClose={closeUpgradeDialog}
        title="Upgrade to Premium"
      >
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-gray-200 mb-2">
              Premium Plan Benefits
            </h4>
            <ul className="space-y-2 text-gray-400">
              <li>• Unlimited cars and build lists</li>
              <li>• Priority customer support</li>
              <li>• Early access to new features</li>
              <li>• Advanced analytics and insights</li>
            </ul>
          </div>

          <div className="bg-gray-800 p-4 rounded">
            <h4 className="font-semibold text-gray-200 mb-2">Pricing</h4>
            <p className="text-2xl font-bold text-yellow-400">$9.99/month</p>
            <p className="text-gray-400">Cancel anytime</p>
          </div>

          {upgradeError && <ErrorAlert message={upgradeError} />}

          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeUpgradeDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpgrade()}
              className="bg-yellow-600 hover:bg-yellow-700"
              disabled={isUpgrading}
            >
              {isUpgrading ? 'Processing...' : 'Upgrade Now'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Cancel Dialog */}
      <Dialog
        isOpen={isCancelDialogOpen}
        onClose={closeCancelDialog}
        title="Cancel Subscription"
      >
        <div className="space-y-4">
          <div>
            <p className="text-gray-300">
              Are you sure you want to cancel your premium subscription? You'll
              continue to have access to premium features until the end of your
              current billing period.
            </p>
          </div>

          {cancelError && <ErrorAlert message={cancelError} />}

          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeCancelDialog} className="bg-gray-600">
              Keep Subscription
            </ActionButton>
            <ActionButton
              onClick={() => void handleCancel()}
              className="bg-red-600 hover:bg-red-700"
              disabled={isCancelling}
            >
              {isCancelling ? 'Cancelling...' : 'Cancel Subscription'}
            </ActionButton>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

export default SubscriptionManagement;
