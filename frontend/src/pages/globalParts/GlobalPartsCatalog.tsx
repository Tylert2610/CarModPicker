import React, { useState, useEffect, useCallback } from 'react';
import { categoriesApi } from '../../services/Api';
import type {
  CategoryResponse,
  GlobalPartReadWithVotes,
} from '../../types/Api';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import GlobalPartList from '../../components/globalParts/GlobalPartList';
import CategoryFilter from '../../components/globalParts/CategoryFilter';
import PageHeader from '../../components/layout/PageHeader';
import AddToBuildListDialog from '../../components/globalParts/AddToBuildListDialog';
import Card from '../../components/common/Card';

const GlobalPartsCatalog: React.FC = () => {
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;
  const [selectedGlobalPart, setSelectedGlobalPart] =
    useState<GlobalPartReadWithVotes | null>(null);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesApi.getCategories();
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  }, []);

  useEffect(() => {
    void loadCategories();
    setLoading(false);
  }, [loadCategories]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedCategory]);

  const handleVoteUpdate = () => {
    // Do nothing - let the VoteButtons component handle optimistic updates
    // This prevents the entire catalog from re-rendering
  };

  const handleAddToBuildList = (globalPart: GlobalPartReadWithVotes) => {
    setSelectedGlobalPart(globalPart);
    setIsAddToBuildListDialogOpen(true);
  };

  const handlePartAdded = () => {
    // Refresh the global parts list if needed
    console.log('Part added to build list');
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedCategory(null);
  };

  const params = {
    skip: (currentPage - 1) * itemsPerPage,
    limit: itemsPerPage,
    category_id: selectedCategory || undefined,
    search: searchTerm || undefined,
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white">
        <PageHeader title="Parts Catalog" />
        <div className="flex justify-center items-center h-64">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title="Parts Catalog" />
        {/* Information Panel */}
        <Card className="mb-6">
          <div className="p-4">
            <h3 className="text-lg font-semibold text-gray-200 mb-3">
              Understanding Global Parts vs Build List Parts
            </h3>
            <div className="grid md:grid-cols-2 gap-4 text-sm text-gray-400">
              <div>
                <h4 className="font-medium text-gray-300 mb-2">
                  🌐 Global Parts (Shared Catalog)
                </h4>
                <ul className="space-y-1">
                  <li>
                    • <strong>Shared</strong> parts available to all users
                  </li>
                  <li>
                    • Can be added to <strong>multiple build lists</strong>
                  </li>
                  <li>
                    • Only <strong>creators or admins</strong> can edit/delete
                  </li>
                  <li>
                    • <strong>Deleting removes from all build lists</strong>
                  </li>
                  <li>• Think of these as the "master catalog"</li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-gray-300 mb-2">
                  📋 Build List Parts (Your Collections)
                </h4>
                <ul className="space-y-1">
                  <li>
                    • <strong>Personal copies</strong> of global parts
                  </li>
                  <li>
                    • Can add <strong>notes and customization</strong>
                  </li>
                  <li>
                    • Only <strong>you can edit/delete</strong> your copies
                  </li>
                  <li>
                    • <strong>Removing doesn't affect other users</strong>
                  </li>
                  <li>• Think of these as "your personal collection"</li>
                </ul>
              </div>
            </div>
            <div className="mt-4 p-3 bg-blue-900/20 border border-blue-700 rounded-lg">
              <p className="text-sm text-blue-300">
                <strong>💡 How it works:</strong> When you add a global part to
                your build list, we create a personal copy (build list part)
                that you can customize. This way, your changes don't affect
                other users' build lists.
              </p>
            </div>
          </div>
        </Card>

        {/* Filters */}
        <div className="mb-8 space-y-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <label htmlFor="search-parts" className="block text-sm font-medium text-gray-300 mb-2">
                Search
              </label>
              <Input
                type="text"
                placeholder="Search parts..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full"
              />
            </div>
            <CategoryFilter
              categories={categories}
              selectedCategory={selectedCategory}
              onCategoryChange={setSelectedCategory}
            />
            <button
              type="button"
              onClick={clearFilters}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>

        {/* Global Parts List */}
        <GlobalPartList
          params={params}
          title="Global Parts Catalog"
          emptyMessage="No parts found. Try adjusting your search or filters."
          showVoteButtons={true}
          onVoteUpdate={handleVoteUpdate}
          showAddToBuildListButton={true}
          onAddToBuildList={handleAddToBuildList}
        />

        {/* Add to Build List Dialog */}
        <AddToBuildListDialog
          isOpen={isAddToBuildListDialogOpen}
          onClose={() => setIsAddToBuildListDialogOpen(false)}
          globalPart={selectedGlobalPart}
          onPartAdded={handlePartAdded}
        />
      </div>
  );
};

export default GlobalPartsCatalog;
