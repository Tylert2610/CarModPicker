import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { usersApi } from '../../api/users';
import type {
  AdminUserUpdate,
  PaginatedResponse,
  UserRead,
} from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import { LoadingOverlay } from '../../components/ui/loading-overlay';
import Pagination from '../../components/ui/pagination';
import Spinner from '../../components/ui/spinner';
import { ADMIN_ITEMS_PER_PAGE } from '../../constants';

const fetchUsersRequestFn = (params?: {
  skip?: number;
  limit?: number;
  search?: string;
}) => usersApi.getAllUsers(params);

const updateUserRequestFn = (payload: {
  userId: string;
  data: AdminUserUpdate;
}) => usersApi.adminUpdateUser(payload.userId, payload.data);

const deleteUserRequestFn = (userId: string) =>
  usersApi.adminDeleteUser(userId);

/** Admin page for viewing user accounts and managing their roles and status. */
function UserManagement() {
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const wasFocusedRef = useRef(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserRead | null>(null);
  const [formData, setFormData] = useState<AdminUserUpdate>({
    username: null,
    email: null,
    disabled: null,
    password: null,
    image_urls: null,
    is_superuser: null,
    is_admin: null,
    email_verified: null,
    subscription_tier: null,
    subscription_status: null,
    subscription_expires_at: null,
  });

  const {
    data: usersData,
    isLoading: isLoadingUsers,
    error: usersError,
    executeRequest: fetchUsers,
  } = useApiRequest<
    PaginatedResponse<UserRead>,
    { skip?: number; limit?: number; search?: string }
  >(fetchUsersRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateUserRequestFn);

  const {
    isLoading: isDeleting,
    error: deleteError,
    executeRequest: executeDelete,
    setError: setDeleteError,
  } = useApiRequest(deleteUserRequestFn);

  useEffect(() => {
    if (currentUser && !currentUser.is_admin) {
      void navigate('/');
    }
  }, [currentUser, navigate]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);

    return () => {
      clearTimeout(timer);
    };
  }, [searchTerm]);

  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearchTerm]);

  useEffect(() => {
    const params: { skip: number; limit: number; search?: string } = {
      skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
      limit: ADMIN_ITEMS_PER_PAGE,
    };
    if (debouncedSearchTerm) {
      params.search = debouncedSearchTerm;
    }
    void fetchUsers(params);
  }, [fetchUsers, currentPage, debouncedSearchTerm]);

  useEffect(() => {
    if (wasFocusedRef.current) {
      requestAnimationFrame(() => {
        const input = document.getElementById(
          'user-search'
        ) as HTMLInputElement;
        if (input && document.activeElement !== input) {
          input.focus();
          if (searchTerm.length > 0) {
            input.setSelectionRange(searchTerm.length, searchTerm.length);
          }
        }
      });
    }
  }, [usersData, searchTerm]);

  const users = usersData?.data || [];
  const pagination = usersData?.pagination;

  if (!currentUser) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="User Management" />
        <Card>
          <ErrorAlert message="Please log in to access user management." />
        </Card>
      </div>
    );
  }

  if (!currentUser.is_admin) {
    return (
      <div>
        <PageHeader title="User Management" />
        <Card>
          <ErrorAlert message="You do not have permission to access user management." />
        </Card>
      </div>
    );
  }

  const handleUpdateUser = async () => {
    if (!selectedUser) return;

    const updateData: AdminUserUpdate = {
      username: formData.username || null,
      email: formData.email || null,
      disabled: formData.disabled ?? null,
      is_admin: formData.is_admin ?? null,
      is_superuser: formData.is_superuser ?? null,
      email_verified: formData.email_verified ?? null,
      image_urls: formData.image_urls || null,
      subscription_tier: formData.subscription_tier ?? null,
      subscription_status: formData.subscription_status ?? null,
      subscription_expires_at: formData.subscription_expires_at || null,
    };

    if (formData.password) {
      updateData.password = formData.password;
    }

    const result = await executeUpdate({
      userId: selectedUser.id,
      data: updateData,
    });
    if (result) {
      setIsEditDialogOpen(false);
      setSelectedUser(null);
      setFormData({
        username: null,
        email: null,
        disabled: null,
        password: null,
        image_urls: null,
        is_superuser: null,
        is_admin: null,
        email_verified: null,
        subscription_tier: null,
        subscription_status: null,
        subscription_expires_at: null,
      });
      void fetchUsers({
        skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
        limit: ADMIN_ITEMS_PER_PAGE,
      });
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    const result = await executeDelete(selectedUser.id);
    if (result) {
      setIsDeleteDialogOpen(false);
      setSelectedUser(null);
      void fetchUsers({
        skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
        limit: ADMIN_ITEMS_PER_PAGE,
      });
    }
  };

  const openEditDialog = (user: UserRead) => {
    setUpdateError(null);
    setSelectedUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      disabled: user.disabled,
      password: null, // Don't populate password
      image_urls: user.image_urls || null,
      is_superuser: user.is_superuser,
      is_admin: user.is_admin,
      email_verified: user.email_verified,
      subscription_tier: user.subscription_tier ?? null,
      subscription_status: user.subscription_status ?? null,
      subscription_expires_at: user.subscription_expires_at ?? null,
    });
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (user: UserRead) => {
    setDeleteError(null);
    setSelectedUser(user);
    setIsDeleteDialogOpen(true);
  };

  const closeEditDialog = () => {
    setIsEditDialogOpen(false);
    setSelectedUser(null);
    setFormData({
      username: null,
      email: null,
      disabled: null,
      password: null,
      image_urls: null,
      is_superuser: null,
      is_admin: null,
      email_verified: null,
      subscription_tier: null,
      subscription_status: null,
      subscription_expires_at: null,
    });
  };

  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setSelectedUser(null);
  };

  const canEditUser = () => {
    return true;
  };

  const canDeleteUser = (user: UserRead) => {
    return user.id !== currentUser.id;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="User Management"
        subtitle="View and manage user accounts"
      />

      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
        <Button variant="secondary" onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </Button>
        <div
          className="flex-1"
          onFocus={() => {
            wasFocusedRef.current = true;
          }}
          onBlur={() => {
            setTimeout(() => {
              if (document.activeElement?.id !== 'user-search') {
                wasFocusedRef.current = false;
              }
            }, 0);
          }}
        >
          <Input
            id="user-search"
            placeholder="Search by username, email, or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {usersError && (
        <Card>
          <ErrorAlert message={`Failed to load users: ${usersError}`} />
        </Card>
      )}

      {/* Results area with loading state */}
      {isLoadingUsers && !usersData ? (
        <Card>
          <div className="flex justify-center items-center py-16">
            <Spinner />
          </div>
        </Card>
      ) : users && users.length > 0 ? (
        <Card className="relative">
          <LoadingOverlay visible={isLoadingUsers} />
          <SectionHeader title="Users" />
          {/* M003/S06 IA decision: 11-col table accepted as horizontal-scroll
              at narrow viewports per M003-UAT.md #5(a) and MEM179. */}
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-border">
                <tr>
                  <th className="p-2 text-foreground">ID</th>
                  <th className="p-2 text-foreground">Username</th>
                  <th className="p-2 text-foreground">Email</th>
                  <th className="p-2 text-foreground">Status</th>
                  <th className="p-2 text-foreground">Email Verified</th>
                  <th className="p-2 text-foreground">2FA</th>
                  <th className="p-2 text-foreground">Sign-in</th>
                  <th className="p-2 text-foreground">Subscription</th>
                  <th className="p-2 text-foreground">Admin</th>
                  <th className="p-2 text-foreground">Superuser</th>
                  <th className="p-2 text-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-border">
                    <td className="p-2 text-foreground">{user.id}</td>
                    <td className="p-2 text-foreground">{user.username}</td>
                    <td className="p-2 text-foreground">{user.email}</td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.disabled
                            ? 'bg-destructive text-destructive-foreground'
                            : 'bg-success text-success-foreground'
                        }`}
                      >
                        {user.disabled ? 'Disabled' : 'Active'}
                      </span>
                    </td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.email_verified
                            ? 'bg-success text-success-foreground'
                            : 'bg-warning text-warning-foreground'
                        }`}
                      >
                        {user.email_verified ? 'Verified' : 'Unverified'}
                      </span>
                    </td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.totp_enabled
                            ? 'bg-success text-success-foreground'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {user.totp_enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </td>
                    <td className="p-2">
                      <div className="flex flex-wrap gap-1">
                        {user.oauth_accounts?.some(
                          (a) => a.provider === 'google'
                        ) && (
                          <span
                            className="px-2 py-1 rounded text-xs bg-info text-info-foreground"
                            title={
                              user.oauth_accounts.find(
                                (a) => a.provider === 'google'
                              )?.email || undefined
                            }
                          >
                            Google
                          </span>
                        )}
                        {!user.oauth_accounts?.length && (
                          <span className="text-muted-foreground text-xs">
                            Password
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.subscription_tier === 'premium'
                            ? 'bg-warning text-warning-foreground'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {user.subscription_tier === 'premium'
                          ? 'Premium'
                          : 'Free'}
                      </span>
                      {user.subscription_tier === 'premium' &&
                        user.subscription_status !== 'active' && (
                          <span className="ml-1 text-xs text-muted-foreground">
                            ({user.subscription_status})
                          </span>
                        )}
                    </td>
                    <td className="p-2">
                      {user.is_admin ? (
                        <span className="px-2 py-1 rounded text-xs bg-info text-info-foreground">
                          Admin
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="p-2">
                      {user.is_superuser ? (
                        <span className="px-2 py-1 rounded text-xs bg-primary text-primary-foreground">
                          Superuser
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="p-2">
                      <div className="flex space-x-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => openEditDialog(user)}
                          disabled={!canEditUser()}
                        >
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => openDeleteDialog(user)}
                          disabled={!canDeleteUser(user)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pagination && (
            <Pagination
              currentPage={pagination.current_page}
              totalPages={pagination.total_pages}
              onPageChange={setCurrentPage}
              itemsPerPage={ADMIN_ITEMS_PER_PAGE}
              totalItems={pagination.total_items}
            />
          )}
        </Card>
      ) : users && users.length === 0 && !isLoadingUsers ? (
        <Card>
          <SectionHeader title="Users" />
          <p className="text-muted-foreground text-center py-8">
            {searchTerm
              ? 'No users found matching your search.'
              : 'No users found.'}
          </p>
        </Card>
      ) : null}

      {/* Edit User Dialog */}
      <Dialog
        open={isEditDialogOpen}
        onOpenChange={(next) => {
          if (!next) closeEditDialog();
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{`Edit User: ${selectedUser?.username ?? ''}`}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <label
                htmlFor="edit-username"
                className="block text-sm font-medium text-foreground"
              >
                Username
              </label>
              <Input
                id="edit-username"
                value={formData.username || ''}
                onChange={(e) =>
                  setFormData({ ...formData, username: e.target.value || null })
                }
                placeholder="Username"
                required
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="edit-email"
                className="block text-sm font-medium text-foreground"
              >
                Email
              </label>
              <Input
                id="edit-email"
                type="email"
                value={formData.email || ''}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value || null })
                }
                placeholder="Email address"
                required
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="edit-password"
                className="block text-sm font-medium text-foreground"
              >
                New Password (leave empty to keep current)
              </label>
              <Input
                id="edit-password"
                type="password"
                value={formData.password || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    password: e.target.value || null,
                  })
                }
                placeholder="New password"
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="edit-image-url"
                className="block text-sm font-medium text-foreground"
              >
                Image URL
              </label>
              <Input
                id="edit-image-url"
                value={formData.image_urls?.[0] || ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    image_urls: e.target.value ? [e.target.value] : null,
                  })
                }
                placeholder="https://example.com/image.jpg"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-disabled"
                  checked={formData.disabled ?? false}
                  onChange={(e) =>
                    setFormData({ ...formData, disabled: e.target.checked })
                  }
                  className="rounded"
                />
                <label htmlFor="edit-disabled" className="text-foreground">
                  Disabled
                </label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-email-verified"
                  checked={formData.email_verified ?? false}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      email_verified: e.target.checked,
                    })
                  }
                  className="rounded"
                />
                <label
                  htmlFor="edit-email-verified"
                  className="text-foreground"
                >
                  Email Verified
                </label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-is-admin"
                  checked={formData.is_admin ?? false}
                  onChange={(e) =>
                    setFormData({ ...formData, is_admin: e.target.checked })
                  }
                  className="rounded"
                  disabled={
                    selectedUser?.id === currentUser.id &&
                    formData.is_admin === true
                  }
                />
                <label htmlFor="edit-is-admin" className="text-foreground">
                  Admin
                </label>
                {selectedUser?.id === currentUser.id && (
                  <span className="text-xs text-muted-foreground">
                    (Cannot remove your own admin status)
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-is-superuser"
                  checked={formData.is_superuser ?? false}
                  onChange={(e) =>
                    setFormData({ ...formData, is_superuser: e.target.checked })
                  }
                  className="rounded"
                  disabled={
                    selectedUser?.id === currentUser.id &&
                    formData.is_superuser === true
                  }
                />
                <label htmlFor="edit-is-superuser" className="text-foreground">
                  Superuser
                </label>
                {selectedUser?.id === currentUser.id && (
                  <span className="text-xs text-muted-foreground">
                    (Cannot remove your own superuser status)
                  </span>
                )}
              </div>
            </div>
            <div className="border-t border-border pt-4 space-y-2">
              <label className="block text-sm text-foreground">
                Subscription tier
              </label>
              <select
                id="edit-subscription-tier"
                value={formData.subscription_tier ?? 'free'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    subscription_tier: e.target.value,
                  })
                }
                className="w-full rounded border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              >
                <option value="free">Free</option>
                <option value="premium">Premium</option>
              </select>
              <label className="block text-sm text-foreground mt-2">
                Subscription status
              </label>
              <select
                id="edit-subscription-status"
                value={formData.subscription_status ?? 'active'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    subscription_status: e.target.value,
                  })
                }
                className="w-full rounded border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              >
                <option value="active">Active</option>
                <option value="cancelled">Cancelled</option>
                <option value="expired">Expired</option>
              </select>
              <div className="space-y-1">
                <label
                  htmlFor="edit-subscription-expires"
                  className="block text-sm font-medium text-foreground"
                >
                  Subscription expires at (leave empty for no expiry)
                </label>
                <Input
                  id="edit-subscription-expires"
                  type="date"
                  value={
                    formData.subscription_expires_at
                      ? formData.subscription_expires_at.slice(0, 10)
                      : ''
                  }
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      subscription_expires_at: e.target.value
                        ? e.target.value
                        : null,
                    })
                  }
                />
              </div>
            </div>
            {updateError && <ErrorAlert message={updateError} />}
            <div className="flex justify-end space-x-2">
              <Button variant="secondary" onClick={closeEditDialog}>
                Cancel
              </Button>
              <Button
                onClick={() => void handleUpdateUser()}
                disabled={isUpdating || !formData.username || !formData.email}
              >
                {isUpdating ? 'Updating...' : 'Update User'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={isDeleteDialogOpen}
        onOpenChange={(next) => {
          if (!next) closeDeleteDialog();
        }}
        onConfirm={() => void handleDeleteUser()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the user{' '}
            <span className="font-semibold text-foreground">
              "{selectedUser?.username || 'user'}"
            </span>
            ? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        cancelLabel="Cancel"
        variant="destructive"
        loading={isDeleting}
        error={deleteError ? `Failed to delete user: ${deleteError}` : null}
      />
    </div>
  );
}

export default UserManagement;
