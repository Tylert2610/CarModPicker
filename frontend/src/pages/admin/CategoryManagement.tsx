import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  CategoryResponse,
  CategoryCreate,
  CategoryUpdate,
} from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Dialog from '../../components/common/Dialog';
import Input from '../../components/common/Input';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';

const fetchCategoriesRequestFn = () =>
  apiClient.get<CategoryResponse[]>('/categories/');
const createCategoryRequestFn = (data: CategoryCreate) =>
  apiClient.post<CategoryResponse>('/categories/', data);
const updateCategoryRequestFn = (payload: {
  categoryId: number;
  data: CategoryUpdate;
}) =>
  apiClient.put<CategoryResponse>(
    `/categories/${payload.categoryId}`,
    payload.data
  );
const deleteCategoryRequestFn = (categoryId: number) =>
  apiClient.delete<Record<string, string>>(`/categories/${categoryId}`);

function CategoryManagement() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] =
    useState<CategoryResponse | null>(null);
  const [formData, setFormData] = useState<CategoryCreate>({
    name: '',
    display_name: '',
    description: '',
    icon: '',
    is_active: true,
    sort_order: 0,
  });

  const {
    data: categories,
    isLoading: isLoadingCategories,
    error: categoriesError,
    executeRequest: fetchCategories,
  } = useApiRequest(fetchCategoriesRequestFn);

  const {
    isLoading: isCreating,
    error: createError,
    executeRequest: executeCreate,
    setError: setCreateError,
  } = useApiRequest(createCategoryRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateCategoryRequestFn);

  const {
    isLoading: isDeleting,
    error: deleteError,
    executeRequest: executeDelete,
    setError: setDeleteError,
  } = useApiRequest(deleteCategoryRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  useEffect(() => {
    void fetchCategories();
  }, [fetchCategories]);

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Category Management" />
        <Card>
          <ErrorAlert message="Please log in to access category management." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Category Management" />
        <Card>
          <ErrorAlert message="You do not have permission to access category management." />
        </Card>
      </div>
    );
  }

  const handleCreateCategory = async () => {
    const result = await executeCreate(formData);
    if (result) {
      setIsCreateDialogOpen(false);
      setFormData({
        name: '',
        display_name: '',
        description: '',
        icon: '',
        is_active: true,
        sort_order: 0,
      });
      void fetchCategories();
    }
  };

  const handleUpdateCategory = async () => {
    if (!selectedCategory) return;
    const result = await executeUpdate({
      categoryId: selectedCategory.id,
      data: formData,
    });
    if (result) {
      setIsEditDialogOpen(false);
      setSelectedCategory(null);
      void fetchCategories();
    }
  };

  const handleDeleteCategory = async () => {
    if (!selectedCategory) return;
    const result = await executeDelete(selectedCategory.id);
    if (result) {
      setIsDeleteDialogOpen(false);
      setSelectedCategory(null);
      void fetchCategories();
    }
  };

  const openCreateDialog = () => {
    setCreateError(null);
    setIsCreateDialogOpen(true);
  };

  const openEditDialog = (category: CategoryResponse) => {
    setUpdateError(null);
    setSelectedCategory(category);
    setFormData({
      name: category.name,
      display_name: category.display_name,
      description: category.description || '',
      icon: category.icon || '',
      is_active: category.is_active,
      sort_order: category.sort_order,
    });
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (category: CategoryResponse) => {
    setDeleteError(null);
    setSelectedCategory(category);
    setIsDeleteDialogOpen(true);
  };

  const closeCreateDialog = () => {
    setIsCreateDialogOpen(false);
    setFormData({
      name: '',
      display_name: '',
      description: '',
      icon: '',
      is_active: true,
      sort_order: 0,
    });
  };

  const closeEditDialog = () => {
    setIsEditDialogOpen(false);
    setSelectedCategory(null);
  };

  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setSelectedCategory(null);
  };

  if (isLoadingCategories && !categories) {
    return (
      <>
        <PageHeader title="Category Management" />
        <LoadingSpinner />
      </>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Category Management"
        subtitle="Create and manage part categories"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
        <ActionButton onClick={openCreateDialog}>
          Create New Category
        </ActionButton>
      </div>

      {categoriesError && (
        <Card>
          <ErrorAlert
            message={`Failed to load categories: ${categoriesError}`}
          />
        </Card>
      )}

      {categories && (
        <Card>
          <SectionHeader title="Categories" />
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-gray-700">
                <tr>
                  <th className="p-2 text-gray-300">Icon</th>
                  <th className="p-2 text-gray-300">Name</th>
                  <th className="p-2 text-gray-300">Display Name</th>
                  <th className="p-2 text-gray-300">Description</th>
                  <th className="p-2 text-gray-300">Status</th>
                  <th className="p-2 text-gray-300">Sort Order</th>
                  <th className="p-2 text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((category) => (
                  <tr key={category.id} className="border-b border-gray-800">
                    <td className="p-2">
                      <span className="text-2xl">{category.icon || '📁'}</span>
                    </td>
                    <td className="p-2 text-gray-200">{category.name}</td>
                    <td className="p-2 text-gray-200">
                      {category.display_name}
                    </td>
                    <td className="p-2 text-gray-400 max-w-xs truncate">
                      {category.description || 'No description'}
                    </td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          category.is_active
                            ? 'bg-green-600 text-green-100'
                            : 'bg-red-600 text-red-100'
                        }`}
                      >
                        {category.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="p-2 text-gray-200">{category.sort_order}</td>
                    <td className="p-2">
                      <div className="flex space-x-2">
                        <ActionButton
                          onClick={() => openEditDialog(category)}
                          className="text-sm px-2 py-1"
                        >
                          Edit
                        </ActionButton>
                        <ActionButton
                          onClick={() => openDeleteDialog(category)}
                          className="text-sm px-2 py-1 bg-red-600 hover:bg-red-700"
                        >
                          Delete
                        </ActionButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Create Category Dialog */}
      <Dialog
        isOpen={isCreateDialogOpen}
        onClose={closeCreateDialog}
        title="Create New Category"
      >
        <div className="space-y-4">
          <Input
            id="create-name"
            label="Name (Internal)"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., engine_parts"
            required
          />
          <Input
            id="create-display-name"
            label="Display Name"
            value={formData.display_name}
            onChange={(e) =>
              setFormData({ ...formData, display_name: e.target.value })
            }
            placeholder="e.g., Engine Parts"
            required
          />
          <Input
            id="create-description"
            label="Description"
            value={formData.description || ''}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            placeholder="Description of this category"
          />
          <Input
            id="create-icon"
            label="Icon (Emoji)"
            value={formData.icon || ''}
            onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
            placeholder="🚗"
          />
          <Input
            id="create-sort-order"
            label="Sort Order"
            type="number"
            value={formData.sort_order}
            onChange={(e) =>
              setFormData({
                ...formData,
                sort_order: parseInt(e.target.value) || 0,
              })
            }
            placeholder="0"
          />
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) =>
                setFormData({ ...formData, is_active: e.target.checked })
              }
              className="rounded"
            />
            <label htmlFor="is_active" className="text-gray-300">
              Active
            </label>
          </div>
          {createError && <ErrorAlert message={createError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeCreateDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleCreateCategory()}
              disabled={isCreating || !formData.name || !formData.display_name}
            >
              {isCreating ? 'Creating...' : 'Create Category'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Edit Category Dialog */}
      <Dialog
        isOpen={isEditDialogOpen}
        onClose={closeEditDialog}
        title={`Edit Category: ${selectedCategory?.display_name}`}
      >
        <div className="space-y-4">
          <Input
            id="edit-name"
            label="Name (Internal)"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., engine_parts"
            required
          />
          <Input
            id="edit-display-name"
            label="Display Name"
            value={formData.display_name}
            onChange={(e) =>
              setFormData({ ...formData, display_name: e.target.value })
            }
            placeholder="e.g., Engine Parts"
            required
          />
          <Input
            id="edit-description"
            label="Description"
            value={formData.description || ''}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            placeholder="Description of this category"
          />
          <Input
            id="edit-icon"
            label="Icon (Emoji)"
            value={formData.icon || ''}
            onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
            placeholder="🚗"
          />
          <Input
            id="edit-sort-order"
            label="Sort Order"
            type="number"
            value={formData.sort_order}
            onChange={(e) =>
              setFormData({
                ...formData,
                sort_order: parseInt(e.target.value) || 0,
              })
            }
            placeholder="0"
          />
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="edit_is_active"
              checked={formData.is_active}
              onChange={(e) =>
                setFormData({ ...formData, is_active: e.target.checked })
              }
              className="rounded"
            />
            <label htmlFor="edit_is_active" className="text-gray-300">
              Active
            </label>
          </div>
          {updateError && <ErrorAlert message={updateError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeEditDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateCategory()}
              disabled={isUpdating || !formData.name || !formData.display_name}
            >
              {isUpdating ? 'Updating...' : 'Update Category'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={isDeleteDialogOpen}
        onClose={closeDeleteDialog}
        onConfirm={() => void handleDeleteCategory()}
        itemName={selectedCategory?.display_name || 'category'}
        itemType="category"
        isProcessing={isDeleting}
        error={deleteError}
      />
    </div>
  );
}

export default CategoryManagement;
